"""«Проспект», дом 7 — игровая версия (Blender): три уровня детализации, развёртки, запекание, glTF в assets.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/prospekt_houses/house7_game.py -- lods|bake|lod2|export|all

  lods   — LOD0 / LOD1 тем же набором частей (kit.py) в игровом режиме + LOD2 (коробка с порталом): одна сетка на уровень,
           поверхность на материал; UV1 в метрах (кубическая проекция), у стекла — 0…1 по проёму; UV2 — атлас грязи;
           цвет вершин — номер окна и штора (шейдер окна) → _asset_src/prospekt_houses/house7/house7_game_v01.blend
  bake   — атлас грязи LOD0 (2K) и LOD1 (1K): R — тёмные потёки и грязь, G — светлое (известь, пыль), B — зелёный налёт у земли
           на севере, A — AO; формулы — dirt() материалов v01 (materials.py), мелкий рисунок кладёт шейдер игры
  lod2   — цвет и грубая нормаль LOD2 (2K) с принятого вида: файл материалов v01 (RING_Prospekt_House7_finish_v01.blend),
           экземпляры в сетки, стекло — тёмное матовое, запекание «выбранное → активное»
  export — поворот на 180° (портал в −Z Godot, как подъезд секции flat_section.gd), glTF + house7.json (габарит, коллизии,
           замки, переключение LOD) → assets/models/prospekt_houses/house7
Заданные бюджеты: LOD0 ≤ 100 тыс. треугольников, LOD1 ≤ 20 тыс., LOD2 ≤ 1,5 тыс.
"""
import json
import math
import os
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit
from kit import B, D, HF, HG, PT, LZ0, LZ1, LSW, LGLASS_Y, GF_FLUTE, GF_PLINTH, GF_TOP
import game_lib as GL
import house7 as H
import house7_finish as FIN

ROOT = "E:/Games/RING-godot"
WORK = ROOT + "/_asset_src/prospekt_houses/house7"
GAME_BLEND = WORK + "/house7_game_v01.blend"
OUT = ROOT + "/assets/models/prospekt_houses/house7"
FINISH = H.LIB + "/models/RING_Prospekt_House7_finish_v01.blend"

LV = [0]                         # уровень детализации, который сейчас собирают построители
PENDING = {}                     # имя модуля → сведения для отсечения и стекла (заполняют построители)
REG = {}                         # имя модуля → сведения после регистрации (кто окно, размер проёма, штора)
OPEN = ("window_glass", "vestibule_glass", "rail_glass", "perf_metal", "notice")
UV_GLASS = ("window_glass", "vestibule_glass", "notice")
# у этих поверхностей своя грязь в атласе UV2; рамы, сталь, цепь, стекло — средняя из угловой клетки
GRIME_MATS = ("panel_beige", "dark_panel", "concrete", "wood", "roof_membrane", "door_steel", "soil")
# игровые слоты (цвета — только для просмотра в Blender; настоящие материалы — шейдеры Godot по имени поверхности)
kit.MATS.update({
    "window_glass": ((0.03, 0.035, 0.04, 1), 0.0, 0.1),
    "vestibule_glass": ((0.02, 0.022, 0.025, 1), 0.0, 0.1),
    "rail_glass": ((0.35, 0.40, 0.40, 1), 0.0, 0.1),
    "roof_membrane": ((0.07, 0.068, 0.066, 1), 0.0, 0.9),
    "door_steel": ((0.06, 0.07, 0.065, 1), 0.3, 0.6),
    "soil": ((0.10, 0.075, 0.05, 1), 0.0, 0.95),
    "lamp_dead": ((0.5, 0.48, 0.44, 1), 0.0, 0.7),
    "chain_steel": ((0.14, 0.14, 0.14, 1), 0.9, 0.5),
    "notice": ((0.8, 0.78, 0.7, 1), 0.0, 0.9),
})

# ---------------------------------------------------------------- игровой режим набора частей: без фасок, листы, учёт коробок
_box, _hull, _cyl, _cylx, _reg = kit.B.box, kit.B.hull, kit.B.cyl, kit.B.cyl_x, kit.register


def g_box(self, x0, x1, y0, y1, z0, z1, mat, bev=0.0, seg=1, rot=None):
    _box(self, x0, x1, y0, y1, z0, z1, mat, 0.0, 1, rot)
    if rot is None and min(x1 - x0, y1 - y0, z1 - z0) >= 1e-5:
        if self.mx is not None:
            x0, x1 = self.mx - x1, self.mx - x0
        self.__dict__.setdefault("aabbs", []).append((x0, x1, y0, y1, z0, z1))


def g_quad(self, x0, x1, z0, z1, y, mat):
    """Лист в плоскости XZ лицом к −Y (стекло, перфорация, объявление)."""
    if self.mx is not None:
        x0, x1 = self.mx - x1, self.mx - x0
    vs = [self.bm.verts.new(p) for p in ((x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1))]
    f = self.bm.faces.new(vs)
    f.material_index = self.mi(mat)


kit.B.box = g_box
kit.B.quad = g_quad
kit.B.hull = lambda self, pts, mat, bev=0.0, seg=1: _hull(self, pts, mat, 0.0, 1)
kit.B.cyl = lambda self, cx, cy, z0, z1, r, mat, seg=20, bev=0.0, r2=None: _cyl(self, cx, cy, z0, z1, r, mat, min(seg, 8 if LV[0] == 0 else 6), 0.0, r2)
kit.B.cyl_x = lambda self, x0, x1, cy, cz, r, mat, seg=14: _cylx(self, x0, x1, cy, cz, r, mat, 6)


def g_register(name, b):
    if name in kit.MODULES:
        return kit.MODULES[name]
    col = _reg(name, b)
    ob = col.objects[0]
    info = PENDING.pop(name, {})
    GL.face_glass_outward(ob, OPEN, info.get("glass_rect"), UV_GLASS)
    GL.cull_module(ob, getattr(b, "aabbs", []), OPEN, info.get("bounds"), info.get("cull_x", (True, True)),
                   info.get("cull_z", (True, True)), info.get("cull_back", True))
    kit.TRIS[name] = GL.tris(ob)
    REG[name] = info
    return col


kit.register = g_register


def g_clad(b, x0, x1, z0, z1, mat="panel_beige", split=1.6, ret_left=False):
    """Участок стены — одна коробка на всю глубину зоны стены: швы плит и подсистема — картами, невидимое уберёт отсечение."""
    b.box(x0, x1, 0, D, z0, z1, mat)


kit.clad = g_clad


def g_panel(w, corner=None, dark=False):
    name = "H_Panel%s_%s" % ("Corner" + corner if corner else "", kit.wkey(w))
    if name in kit.MODULES:
        return name
    b = B(name, mirror_w=(w if corner == "R" else None))
    dep = 1.5 if corner else D                     # у угла возврат на торец 1,5 м, дальше — пролёт торца
    b.box(0, w, 0, dep, 0, HF, "dark_panel" if dark else "panel_beige")
    cx = (False, True) if corner == "L" else ((True, False) if corner == "R" else (True, True))
    PENDING[name] = dict(bounds=(w, dep, HF), cull_x=cx)
    kit.register(name, b)
    return name


WIN_TILE = {"a": 1, "b": 4, "c": 2, "d": 3}          # 0 — без шторы; 1 задёрнуты, 2 по краям, 3 тюль, 4 жалюзи (атлас curtains.png)
LOG_TILE = {"a": 1, "b": 2, "c": 2}


def g_window(w, end=False, variant=None):
    name = "H_Window%s%s_%s" % ("End" if end else "", "_" + variant if variant else "", kit.wkey(w))
    if name in kit.MODULES:
        return name
    b = B(name)
    mat = "dark_panel" if end else "panel_beige"
    ow = (w - 0.4) if end else 3.0
    x0 = (w - ow) / 2
    x1 = x0 + ow
    zs, ze = 0.6, 2.7
    g_clad(b, 0, w, 0, zs, mat)
    g_clad(b, 0, w, ze, HF, mat)
    g_clad(b, 0, x0, zs, ze, mat)
    g_clad(b, x1, w, zs, ze, mat)
    gz0 = zs + 0.03
    if LV[0] == 0:
        b.box(x0 - 0.03, x1 + 0.03, -0.05, 0.25, zs, zs + 0.03, "alu_frame")          # отлив
        fr, y0, y1 = 0.065, 0.25, 0.32
        b.box(x0, x0 + fr, y0, y1, gz0, ze, "alu_frame")
        b.box(x1 - fr, x1, y0, y1, gz0, ze, "alu_frame")
        b.box(x0 + fr, x1 - fr, y0, y1, gz0, gz0 + fr, "alu_frame")
        b.box(x0 + fr, x1 - fr, y0, y1, ze - fr, ze, "alu_frame")
        for ix in (x0 + 0.8, x1 - 0.8):                                               # импосты створок
            b.box(ix - fr * 0.6, ix + fr * 0.6, y0, y1, gz0 + fr, ze - fr, "alu_frame")
        sf = 0.04                                                                      # рамки двух створок — простым профилем
        for (sx0, sx1) in ((x0 + fr, x0 + 0.8 - fr * 0.6), (x1 - 0.8 + fr * 0.6, x1 - fr)):
            sz0, sz1 = gz0 + fr, ze - fr
            for (a0, a1, c0, c1) in ((sx0, sx0 + sf, sz0, sz1), (sx1 - sf, sx1, sz0, sz1),
                                     (sx0 + sf, sx1 - sf, sz0, sz0 + sf), (sx0 + sf, sx1 - sf, sz1 - sf, sz1)):
                b.box(a0, a1, 0.22, 0.25, c0, c1, "alu_frame")
        gy = 0.285
    else:
        gz0, gy = zs, 0.20
    b.quad(x0, x1, gz0, ze, gy, "window_glass")
    PENDING[name] = dict(bounds=(w, D, HF), glass_rect=(x0, x1, gz0, ze), kind="window",
                         tile=WIN_TILE.get(variant, 0), size=(ow, ze - gz0))
    kit.register(name, b)
    return name


def g_loggia(b, w, glass, variant):
    wood_w = 0.6
    g_clad(b, 0, w, 0, LZ0, "panel_beige")
    g_clad(b, 0, w, LZ1, HF, "dark_panel")
    g_clad(b, 0, LSW, LZ0, LZ1, "panel_beige")
    g_clad(b, w - LSW, w, LZ0, LZ1, "panel_beige")
    xr = w - LSW
    b.box(LSW, w - LSW, 0.02, 1.40, LZ0, LZ0 + 0.015, "concrete")                     # пол ниши
    b.box(LSW, w - LSW, 1.34, 1.40, LZ0 + 0.015, LZ1, "dark_panel")                    # задняя стенка за остеклением
    b.box(LSW, LSW + 0.01, 0.10, 1.34, LZ0 + 0.015, LZ1, "dark_panel")                 # левая стенка
    b.box(xr - 0.03, xr, 0.10, 1.12, LZ0 + 0.02, LZ1 - 0.02, "wood")                   # рейки правой стенки — карта дерева
    if LV[0] == 0:                                                                     # рейки на задней стене — геометрией
        b.box(xr - wood_w, xr, LGLASS_Y + 0.03, 1.34, LZ0 + 0.015, LZ1, "dark_panel")
        xs = xr - wood_w + 0.01
        while xs + 0.045 < xr:
            b.box(xs, xs + 0.045, LGLASS_Y, LGLASS_Y + 0.03, LZ0 + 0.03, LZ1 - 0.03, "wood")
            xs += 0.06
    else:
        b.box(xr - wood_w, xr, LGLASS_Y, LGLASS_Y + 0.03, LZ0 + 0.03, LZ1 - 0.03, "wood")  # полоса дерева на задней стене
    gx0, gx1 = LSW + 0.02, xr - wood_w - 0.02
    gz0, gz1 = LZ0 + 0.02, LZ1 - 0.04
    if LV[0] == 0:
        fr, y0, y1 = 0.06, LGLASS_Y, LGLASS_Y + 0.07
        b.box(gx0, gx0 + fr, y0, y1, gz0, gz1, "alu_frame")
        b.box(gx1 - fr, gx1, y0, y1, gz0, gz1, "alu_frame")
        b.box(gx0 + fr, gx1 - fr, y0, y1, gz0, gz0 + fr, "alu_frame")
        b.box(gx0 + fr, gx1 - fr, y0, y1, gz1 - fr, gz1, "alu_frame")
        imp = gx0 + (gx1 - gx0) * 0.45
        b.box(imp - fr * 0.6, imp + fr * 0.6, y0, y1, gz0 + fr, gz1 - fr, "alu_frame")
        b.box(gx0 + fr, gx1 - fr, y0, y1, 2.15 - fr * 0.5, 2.15 + fr * 0.5, "alu_frame")
        b.quad(gx0, gx1, gz0, gz1, LGLASS_Y + 0.035, "window_glass")
    else:
        b.quad(gx0, gx1, gz0, gz1, LGLASS_Y, "window_glass")
    # ограждение 1,1 м
    y0, y1 = 0.04, 0.09
    zb, zt = LZ0, LZ0 + 1.10
    xa, xb = LSW + 0.005, w - LSW - 0.005
    if not glass:
        if LV[0] == 0:
            b.box(xa, xa + 0.04, y0, y1, zb, zt, "alu_frame")
            b.box(xb - 0.04, xb, y0, y1, zb, zt, "alu_frame")
            b.box(xa + 0.04, xb - 0.04, y0, y1, zt - 0.04, zt, "alu_frame")
            b.box(xa + 0.04, xb - 0.04, y0, y1, zb + 0.02, zb + 0.06, "alu_frame")
            b.quad(xa + 0.04, xb - 0.04, zb + 0.06, zt - 0.04, 0.0615, "perf_metal")
        else:
            b.quad(xa, xb, zb, zt, 0.0615, "perf_metal")
    else:
        if LV[0] == 0:
            n = 3
            px = [xa + (xb - xa - 0.04) * i / n for i in range(n + 1)]
            for p in px:
                b.box(p, p + 0.04, y0, y1, zb, zt, "steel")
            b.box(xa, xb, 0.05, 0.11, zb + 0.04, zb + 0.10, "steel")
            b.cyl_x(xa, xb, 0.065, zt, 0.025, "steel")
            for i in range(n):
                b.quad(px[i] + 0.06, px[i + 1] - 0.02, zb + 0.10, zt - 0.04, 0.065, "rail_glass")
        else:
            b.box(xa, xb, 0.05, 0.11, zb, zb + 0.10, "steel")
            b.quad(xa, xb, zb + 0.10, zt, 0.065, "rail_glass")
    return (gx0, gx1, gz0, gz1)


def _loggia_mod(w, glass, variant):
    name = "H_Loggia%s%s_%s" % ("Glass" if glass else "Perf", "_" + variant if variant else "", kit.wkey(w))
    if name in kit.MODULES:
        return name
    b = B(name)
    r = g_loggia(b, w, glass, variant)
    PENDING[name] = dict(bounds=(w, D, HF), glass_rect=r, kind="loggia", tile=LOG_TILE.get(variant, 0),
                         size=(r[1] - r[0], r[3] - r[2]))
    kit.register(name, b)
    return name


kit.mod_panel = g_panel
kit.mod_window = g_window
kit.mod_loggia_perf = lambda w, variant=None: _loggia_mod(w, False, variant)
kit.mod_loggia_glass = lambda w, variant=None: _loggia_mod(w, True, variant)


def g_pilaster(h=HG):
    name = "H_GroundPilaster"
    if name in kit.MODULES:
        return name
    b = B(name)
    if LV[0] == 0:
        b.box(0.0, 0.5, -0.45, 0.20, 0.15, h - 0.15, "concrete")
        b.box(-0.03, 0.53, -0.48, 0.20, 0.0, 0.15, "concrete")
        b.box(-0.03, 0.53, -0.48, 0.20, h - 0.15, h, "concrete")
    else:
        b.box(0.0, 0.5, -0.45, 0.20, 0.0, h, "concrete")
    PENDING[name] = dict(bounds=(0.5, 0.20, h), cull_x=(False, False))
    kit.register(name, b)
    return name


def g_corner_post(h=HG):
    name = "H_GroundCornerPost"
    if name in kit.MODULES:
        return name
    b = B(name)
    if LV[0] == 0:
        b.box(-0.45, 0.50, -0.45, 0.50, 0.15, h - 0.15, "concrete")
        b.box(-0.48, 0.53, -0.48, 0.53, 0.0, 0.15, "concrete")
        b.box(-0.48, 0.53, -0.48, 0.53, h - 0.15, h, "concrete")
    else:
        b.box(-0.45, 0.50, -0.45, 0.50, 0.0, h, "concrete")
    PENDING[name] = dict(bounds=(0.5, 0.50, h), cull_x=(False, False), cull_back=False)
    kit.register(name, b)
    return name


def g_ground_field(w, h=HG):
    name = "H_GroundField_%s" % kit.wkey(w)
    if name in kit.MODULES:
        return name
    b = B(name)
    b.box(0, w, GF_FLUTE, D, 0, h, "concrete")
    b.box(0, w, 0.0, GF_FLUTE, 0, GF_PLINTH, "concrete")
    b.box(0, w, 0.0, GF_FLUTE, h - GF_TOP, h, "concrete")
    if LV[0] == 0:
        n = max(1, round(w / 0.28))
        p = w / n
        rw = p * 0.64
        for i in range(n):
            xc = (i + 0.5) * p
            b.box(xc - rw / 2, xc + rw / 2, 0.0, GF_FLUTE, GF_PLINTH, h - GF_TOP, "concrete")
    side = w < 2.9                                  # поля 3,0 и 5,0 у портала: торцы открыты к вестибюлю
    PENDING[name] = dict(bounds=(w, D, h), cull_x=(side, side), cull_z=(True, False))
    kit.register(name, b)
    return name


def g_belt(L):
    name = "H_BaseBelt_%s" % kit.wkey(L)
    if name in kit.MODULES:
        return name
    b = B(name)
    b.box(0, L, -0.06, 0.20, 0.0, 0.18, "dark_panel")
    b.box(0, L, -0.07, 0.20, 0.18, 0.21, "alu_frame")
    kit.register(name, b)
    return name


def g_parapet(L):
    name = "H_Parapet_%s" % kit.wkey(L)
    if name in kit.MODULES:
        return name
    b = B(name)
    if LV[0] == 0:
        b.box(0, L, 0.0, 0.25, 0.0, 0.41, "dark_panel")
        b.box(0, L, 0.0, 0.30, 0.41, 0.45, "alu_frame")
    else:
        b.box(0, L, 0.0, 0.30, 0.0, 0.45, "dark_panel")
    kit.register(name, b)
    return name


kit.mod_ground_pilaster = g_pilaster
kit.mod_corner_post = g_corner_post
kit.mod_ground_field = g_ground_field
kit.mod_belt = g_belt
kit.mod_parapet = g_parapet


# ---------------------------------------------------------------- свои узлы дома 7 в игровом виде
def g_portal():
    HX, HY, P0, P1 = H.HX, H.HY, H.PORTAL[0], H.PORTAL[1]
    b = B("H7_PortalCanopy")
    y_f = -HY - H.PORTAL_OUT
    b.box(P0, P1, y_f, -HY + 0.3, 4.20, HG, "concrete")
    b.box(P0, P1, y_f, y_f + 0.32, 3.50, 4.65, "concrete")
    for i in range(7):
        xc = -6.0 + 2.0 * i
        b.hull([(xc - 1.1 - 0.16, -HY, 3.85), (xc - 1.1 + 0.16, -HY, 3.85), (xc - 1.1 - 0.16, -HY, 4.20), (xc - 1.1 + 0.16, -HY, 4.20),
                (xc - 0.16, y_f + 0.32, 3.85), (xc + 0.16, y_f + 0.32, 3.85), (xc - 0.16, y_f + 0.32, 4.20), (xc + 0.16, y_f + 0.32, 4.20)],
               "concrete")
    if LV[0] == 0:
        for xc in (-6.0, -4.0, -2.0, 0.0, 2.0, 4.0):                       # мёртвые светильники под козырьком
            b.cyl(xc + 1.0, -14.2, 4.14, 4.20, 0.11, "steel")
            b.cyl(xc + 1.0, -14.2, 4.125, 4.14, 0.085, "lamp_dead")
        b.box(P0 - 0.03, P1 + 0.03, y_f - 0.03, y_f + 0.25, 4.65, 4.69, "steel")
    kit.register("H7_PortalCanopy", b)
    for side, sgn in (("L", -1), ("R", 1)):
        b = B("H7_PortalPylon" + side)
        X = lambda x: sgn * x
        top = [(X(6.9), -15.2, 4.2), (X(5.3), -15.2, 4.2), (X(5.3), -13.0, 4.2), (X(6.9), -13.0, 4.2)]
        base = [(X(6.9), -14.4, 0.0), (X(4.2), -14.4, 0.0), (X(4.2), -13.0, 0.0), (X(6.9), -13.0, 0.0)]
        b.hull(top + base + [(X(4.55), -15.0, 1.8)], "concrete")
        kit.register("H7_PortalPylon" + side, b)
    b = B("H7_PortalCore")
    b.box(-4.0, 2.0, -HY, -HY + D, 3.45, HG, "concrete")
    b.box(-4.0, 2.0, -HY, -HY + D, 0.0, 0.15, "concrete")
    kit.register("H7_PortalCore", b)
    # витраж вестибюля: рамы и один лист стекла на весь проём (за ним шейдер рисует тёмный вестибюль глубиной 4 м)
    b = B("H7_PortalGlazing")
    yf0, yf1 = -12.52, -12.40
    ym = (yf0 + yf1) / 2
    x0, x1, z0, z1 = -4.0, 2.0, 0.15, 3.45
    fr = 0.06
    b.box(x0, x0 + fr, yf0, yf1, z0, z1, "alu_frame")
    b.box(x1 - fr, x1, yf0, yf1, z0, z1, "alu_frame")
    b.box(x0 + fr, x1 - fr, yf0, yf1, z1 - fr, z1, "alu_frame")
    b.box(x0 + fr, x1 - fr, yf0, yf1, z0, z0 + 0.12, "alu_frame")
    dx0, dx1 = -2.17, 0.17
    for xm in (dx0, dx1):
        b.box(xm - 0.04, xm + 0.04, yf0 - 0.02, yf1 + 0.02, z0 + 0.12, z1 - fr, "alu_frame")
    if LV[0] == 0:
        b.box(x0 + fr, x1 - fr, yf0 - 0.02, yf1 + 0.02, 2.55 - 0.05, 2.55 + 0.05, "alu_frame")
        for (xa, xb) in ((x0 + fr, dx0 - 0.04), (dx1 + 0.04, x1 - fr)):
            b.box(xa, xb, yf0, yf1, 1.0 - 0.03, 1.0 + 0.03, "alu_frame")
        dz0, dz1 = z0 + 0.12, z0 + 0.12 + 2.42
        for (xa, xb) in ((dx0 + 0.04, -1.0 - 0.01), (-1.0 + 0.01, dx1 - 0.04)):
            yl0, yl1 = yf0 - 0.04, yf1
            b.box(xa, xa + 0.09, yl0, yl1, dz0, dz1, "alu_frame")
            b.box(xb - 0.09, xb, yl0, yl1, dz0, dz1, "alu_frame")
            b.box(xa + 0.09, xb - 0.09, yl0, yl1, dz1 - 0.09, dz1, "alu_frame")
            b.box(xa + 0.09, xb - 0.09, yl0, yl1, dz0, dz0 + 0.20, "alu_frame")
        for xh in (-1.0 - 0.12, -1.0 + 0.12):                              # ручки-скобы
            b.cyl(xh, yf0 - 0.10, 0.85, 1.55, 0.016, "steel", seg=6)
            for zz in (0.9, 1.5):
                b.box(xh - 0.012, xh + 0.012, yf0 - 0.10, yf0 - 0.04, zz - 0.012, zz + 0.012, "steel")
    b.quad(x0 + fr, x1 - fr, z0 + 0.12, z1 - fr, ym, "vestibule_glass")
    PENDING["H7_PortalGlazing"] = dict(glass_rect=(x0 + fr, x1 - fr, z0 + 0.12, z1 - fr), kind="vestibule", tile=0,
                                       size=(x1 - x0 - 2 * fr, z1 - z0 - 0.12 - fr))
    kit.register("H7_PortalGlazing", b)
    # ступенчатая клумба: три террасы, земля на 5 см ниже кромки
    b = B("H7_PortalBeds")
    X0, X1, wt = 2.3, 5.7, 0.14
    for (h, ya, yb) in ((1.35, -HY, -HY - 0.7), (0.90, -HY - 0.7, -HY - 1.4), (0.45, -HY - 1.4, -HY - 2.1)):
        if LV[0] == 0:
            b.box(X0 + wt, X1 - wt, yb + wt, ya, 0.0, h - 0.30, "concrete")
            b.box(X0, X0 + wt, yb, ya, 0.0, h, "concrete")
            b.box(X1 - wt, X1, yb, ya, 0.0, h, "concrete")
            b.box(X0 + wt, X1 - wt, yb, yb + wt, 0.0, h, "concrete")
            b.box(X0 + wt, X1 - wt, yb + wt, ya, h - 0.30, h - 0.05, "soil")
        else:
            b.box(X0, X1, yb, ya, 0.0, h, "concrete")
    kit.register("H7_PortalBeds", b)


def g_service_door():
    """Служебная дверь на севере: бетонная панель с проёмом, стальная дверь, накладка с проушиной под замок (координаты модуля)."""
    b = B("H7_ServiceDoor")
    w, h = 2.5, HG
    ox0, ox1, oh = 0.625, 1.875, 2.5
    b.box(0, ox0, 0.0, D, 0, h, "concrete")
    b.box(ox1, w, 0.0, D, 0, h, "concrete")
    b.box(ox0, ox1, 0.0, D, oh, h, "concrete")
    lx0, lx1 = 1.25 - 0.585, 1.25 + 0.585
    b.box(lx0, lx1, 0.21, 0.26, 0.04, 2.46, "door_steel")
    b.box(ox0, ox1, 0.26, D, 0.0, oh, "concrete")                             # глухо за полотном
    if LV[0] == 0:
        fx0, fx1 = ox0, ox1
        b.box(fx0, fx0 + 0.04, 0.16, 0.30, 0.0, oh, "steel")
        b.box(fx1 - 0.04, fx1, 0.16, 0.30, 0.0, oh, "steel")
        b.box(fx0 + 0.04, fx1 - 0.04, 0.16, 0.30, oh - 0.04, oh, "steel")
        b.box(lx1 - 0.18, lx1 - 0.05, 0.17, 0.21, 1.0, 1.04, "steel")             # ручка-нажим
        b.box(1.665, 1.775, 0.185, 0.212, 0.98, 1.06, "steel")                    # накладка на полотне
        b.box(1.80, 1.90, 0.135, 0.165, 0.98, 1.06, "steel")                      # проушина на коробке
        b.box(1.745, 1.775, 0.150, 0.190, 1.005, 1.035, "steel")                  # петля накладки
        cx0, cx1 = 0.35, 2.15
        b.hull([(cx0, 0.0, 2.95), (cx1, 0.0, 2.95), (cx0, -0.70, 2.78), (cx1, -0.70, 2.78),
                (cx0, 0.0, 2.955), (cx1, 0.0, 2.955), (cx0, -0.70, 2.785), (cx1, -0.70, 2.785)], "steel")
    PENDING["H7_ServiceDoor"] = dict(bounds=(w, D, h))
    kit.register("H7_ServiceDoor", b)


def g_roof():
    z, HX, HY = H.H_ROOF, H.HX, H.HY
    b = B("H7_Roof")
    b.box(-HX + 0.25, HX - 0.25, -HY + 0.25, HY - 0.25, z - 0.20, z, "concrete")
    b.box(-HX + 0.50, HX - 0.50, -HY + 0.50, HY - 0.50, z, z + 0.04, "roof_membrane")
    for xc in (-7.5, 7.5):
        x0, x1, y0, y1 = xc - 3.0, xc + 3.0, 0.0, 5.0
        z0, z1 = z + 0.04, z + 0.04 + 3.0
        b.box(x0, x1, y0, y1, z0, z1, "dark_panel")
        b.box(x0 - 0.12, x1 + 0.12, y0 - 0.12, y1 + 0.12, z1, z1 + 0.14, "concrete")
        if LV[0] == 0:
            b.box(xc - 0.64, xc + 0.64, y0 - 0.03, y0 + 0.06, z0, z0 + 2.46, "steel")
            b.box(xc - 0.585, xc + 0.585, y0 - 0.015, y0 + 0.07, z0 + 0.04, z0 + 2.46, "door_steel")
            for sx, nx in ((x0, -1), (x1, 1)):
                yc, fw, fh, fz = 2.5, 2.0, 1.0, z0 + 1.5
                for (ya, yb, za, zb) in ((yc - fw / 2, yc + fw / 2, fz, fz + 0.05), (yc - fw / 2, yc + fw / 2, fz + fh - 0.05, fz + fh),
                                         (yc - fw / 2, yc - fw / 2 + 0.05, fz, fz + fh), (yc + fw / 2 - 0.05, yc + fw / 2, fz, fz + fh)):
                    b.box(min(sx, sx + nx * 0.04), max(sx, sx + nx * 0.04), ya, yb, za, zb, "steel")
                for k in range(7):
                    zz = fz + 0.12 + k * 0.125
                    b.box(min(sx, sx + nx * 0.03), max(sx, sx + nx * 0.03), yc - fw / 2 + 0.05, yc + fw / 2 - 0.05,
                          zz - 0.045, zz + 0.045, "steel", rot=("Y", nx * math.radians(38)))
    for (vx, vy) in ((-14.0, 8.0), (14.0, 8.0), (-1.0, -7.0), (11.0, -7.0)):
        b.cyl(vx, vy, z + 0.04, z + 1.5, 0.35, "galvanized" if "galvanized" in kit.MATS else "steel")
        if LV[0] == 0:
            b.cyl(vx, vy, z + 1.5, z + 1.56, 0.50, "steel", r2=0.50)
    ax, ay = 0.0, 9.5
    b.cyl(ax, ay, z + 0.04, z + 6.2, 0.045, "steel", seg=6)
    if LV[0] == 0:
        b.box(ax - 0.4, ax + 0.4, ay - 0.4, ay + 0.4, z + 0.04, z + 0.19, "concrete")
        for zz, L in ((z + 3.2, 0.8), (z + 4.4, 0.65), (z + 5.6, 0.5)):
            b.box(ax - L, ax + L, ay - 0.012, ay + 0.012, zz - 0.012, zz + 0.012, "steel")
    kit.register("H7_Roof", b)


kit.MATS["galvanized"] = ((0.45, 0.46, 0.47, 1), 0.9, 0.45)


# ---------------------------------------------------------------- цепь и объявление (только LOD0)
def chain_object():
    """Цепь — одна сетка звеньев (звено: «стадион» 40 × 25 мм, 6 точек контура × 3 грани прутка), путь — FIN.chain_frames()."""
    frames = FIN.chain_frames()
    R, S, rr = 0.0095, 0.0075, 0.003
    loop = []
    for k in range(3):
        a = -math.pi / 2 + math.pi * k / 2
        loop.append((S + R * math.cos(a), R * math.sin(a)))
    for k in range(3):
        a = math.pi / 2 + math.pi * k / 2
        loop.append((-S + R * math.cos(a), R * math.sin(a)))
    bm = bmesh.new()
    for (p, rot, tg) in frames:
        M = Matrix.Translation(p) @ rot.to_4x4()
        rings = []
        n = len(loop)
        for i, (px, py) in enumerate(loop):
            nx, ny = loop[(i + 1) % n][0] - loop[i - 1][0], loop[(i + 1) % n][1] - loop[i - 1][1]
            L = math.hypot(nx, ny)
            ox, oy = ny / L, -nx / L
            ring = []
            for q in range(3):
                t = 2 * math.pi * q / 3
                ring.append(bm.verts.new(M @ Vector((px + ox * rr * math.cos(t), py + oy * rr * math.cos(t), rr * math.sin(t)))))
            rings.append(ring)
        for i in range(n):
            for q in range(3):
                bm.faces.new((rings[i][q], rings[i][(q + 1) % 3], rings[(i + 1) % n][(q + 1) % 3], rings[(i + 1) % n][q]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("chain")
    bm.to_mesh(me)
    bm.free()
    for f in me.polygons:
        f.use_smooth = True
    me.materials.append(kit.get_mat("chain_steel"))
    return bpy.data.objects.new("chain", me), FIN.lock_hang_point(frames)


def notice_object():
    """Лист «ПОДЪЕЗД ЗАКРЫТ»: в игре стекло непрозрачное (комната — шейдером), поэтому лист на 8 мм снаружи стекла."""
    x0, x1, z0, z1, y = -1.95, -1.74, 1.56, 1.857, -12.468
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    f = bm.faces.new([bm.verts.new(p) for p in ((x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1))])
    for l, uv in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        l[uvl].uv = uv
    me = bpy.data.meshes.new("notice")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(kit.get_mat("notice"))
    return bpy.data.objects.new("notice", me)


# ---------------------------------------------------------------- сборка уровня детализации
def color_of(e):
    """Цвет вершин экземпляра: R — штора (0 нет, 0,25…1 — плитка атласа 1…4), G — случайное число окна, B / A — ширина и
    высота проёма / 8 (размер «комнаты» шейдера)."""
    info = REG.get(e.instance_collection.name.split(".")[0], {})
    seed = GL.inst_seed(e.name)
    if info.get("kind") in ("window", "loggia", "vestibule"):
        w, h = info["size"]
        return (info["tile"] / 4.0, seed, w / 8.0, h / 8.0)
    return (0.0, seed, 0.0, 0.0)


def build_lod(lv):
    LV[0] = lv
    kit.MODULES.clear()
    kit.TRIS.clear()
    REG.clear()
    root = bpy.context.scene.collection
    mods = bpy.data.collections.new("Модули_LOD%d" % lv)
    root.children.link(mods)
    kit.set_root(mods)
    asm = bpy.data.collections.new("Сборка_LOD%d" % lv)
    root.children.link(asm)
    H.build_kit()
    g_portal()
    g_service_door()
    g_roof()
    for k in ("H7_PortalCanopy", "H7_PortalPylonL", "H7_PortalPylonR", "H7_PortalCore", "H7_PortalGlazing", "H7_PortalBeds", "H7_Roof"):
        kit.inst(asm, k, (0, 0, 0), 0, k)
    H.ground_floor(asm)
    H.upper_floors(asm, "S", H.SOUTH)
    H.upper_floors(asm, "N", H.NORTH)
    H.upper_floors(asm, "E", H.END)
    H.upper_floors(asm, "W", H.END)
    H.parapets(asm)
    H.belts(asm)
    extra = []
    lock = None
    if lv == 0:
        ch, lock = chain_object()
        extra = [ch, notice_object()]
    ob = GL.realize(asm, "house7_lod%d" % lv, color_of, extra)
    # грани вниз у земли не видны никогда
    GL.drop_faces(ob, lambda c, n, m: n.z < -0.9 and c.z < 0.02)
    GL.merge_slots_drop_unused(ob)
    GL.box_uv(ob, skip_mats=UV_GLASS, rotate_mats=("wood",))
    mods_lc = bpy.context.view_layer.layer_collection.children[mods.name]
    mods_lc.exclude = True
    bpy.context.view_layer.layer_collection.children[asm.name].exclude = True
    return ob, lock


def build_lod2():
    """Коробка дома с порталом, клумбой и машинными на кровле — под запечённый цвет и нормаль фасада (2K)."""
    HX, HY, top = H.HX, H.HY, H.H_TOP
    bm = bmesh.new()

    def box(x0, x1, y0, y1, z0, z1, bottom=False):
        r = bmesh.ops.create_cube(bm, size=1.0)
        for v in r["verts"]:
            v.co = Vector(((x0 + x1) / 2 + v.co.x * (x1 - x0), (y0 + y1) / 2 + v.co.y * (y1 - y0), (z0 + z1) / 2 + v.co.z * (z1 - z0)))
        if not bottom:
            kill = [f for f in {f for v in r["verts"] for f in v.link_faces} if f.normal.z < -0.9 and f.calc_center_median().z < 0.05]
            bmesh.ops.delete(bm, geom=kill, context="FACES")

    box(-HX, HX, -HY, HY, 0.0, top)
    box(-7.0, 7.0, -15.4, -HY, 3.5, 4.69, bottom=True)          # козырёк
    box(-6.9, -4.4, -15.0, -HY, 0.0, 4.2)                        # пилоны
    box(4.4, 6.9, -15.0, -HY, 0.0, 4.2)
    box(2.3, 5.7, -15.1, -HY, 0.0, 0.9)                          # клумба (средняя высота)
    for xc in (-7.5, 7.5):
        box(xc - 3.12, xc + 3.12, -0.12, 5.12, H.H_ROOF, H.H_ROOF + 3.18)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("house7_lod2")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(kit.get_mat("panel_beige"))
    ob = bpy.data.objects.new("house7_lod2", me)
    bpy.context.scene.collection.objects.link(ob)
    GL.atlas_uv(ob, layer="UVMap", margin=0.01, angle=45.0)
    return ob


def stage_lods():
    os.makedirs(WORK, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    report = {}
    lod0, lock = build_lod(0)
    lod1, _ = build_lod(1)
    for ob in (lod0, lod1):
        GL.atlas_uv(ob, "UV2", only_mats=GRIME_MATS)
    lod2 = build_lod2()
    for ob in (lod0, lod1, lod2):
        report[ob.name] = dict(tris=GL.tris(ob), surfaces=len(ob.data.materials), by_material=GL.tris_by_material(ob))
    report["house7_lod0"]["uv2_fill"] = round(GL.uv_fill(lod0, "UV2"), 3)
    report["house7_lod1"]["uv2_fill"] = round(GL.uv_fill(lod1, "UV2"), 3)
    report["lock_chain_blender"] = list(lock)
    bpy.ops.wm.save_as_mainfile(filepath=GAME_BLEND)
    with open(WORK + "/lods_report.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("LODS", json.dumps({k: (v["tris"] if isinstance(v, dict) else v) for k, v in report.items()}))


# ---------------------------------------------------------------- атлас грязи (UV2)
def grime_rgb(N):
    """Места грязи по форме — те же слагаемые, что dirt() материалов v01, без мелкого рисунка (его кладёт шейдер игры по UV1):
    R — тёмное: брызги у земли, потёки под швами и перекрытиями в укрытых местах, грязь в углах;
    G — светлое: известь под плитами в укрытии, пыль на горизонтальных гранях; B — зелёный налёт у земли на севере."""
    import materials as MT
    z = N.pos.outputs[2]
    rag = N.r(N.tri("masks/m_grain.png", 0.55, "Non-Color", off=(0.37, 0.11)))
    zr = N.math("ADD", z, N.math("MULTIPLY", N.math("SUBTRACT", rag, 0.35), 0.7))
    splash = N.rng(zr, 0.15, 0.80, 0.9, 0.0)
    seam = N.math("POWER", N.math("FRACT", N.math("DIVIDE", N.math("SUBTRACT", z, 4.5), 3.0)), 1.5)
    gate = N.rng(N.r(N.tri("masks/m_plaque.png", 9.0, "Non-Color", off=(0.2, 0.6))), 0.03, 0.4, 0.0, 1.0)
    shelter = N.math("ADD", 0.3, N.math("MULTIPLY", 0.7, N.math("SUBTRACT", 1.0, N.ao(1.0))))
    streak = N.math("MULTIPLY", N.math("MULTIPLY", seam, gate), N.math("MULTIPLY", shelter, 1.2))
    crev = N.math("MULTIPLY", N.math("SUBTRACT", 1.0, N.ao(0.28)), 0.6)
    r = N.math("MINIMUM", N.math("ADD", N.math("ADD", splash, streak), crev), 1.0)
    lime = N.math("MULTIPLY", N.rng(N.r(N.tri("masks/m_streak.png", 2.6, "Non-Color", vst=1.8, off=(0.2, 0.55))), 0.25, 0.8, 0.0, 1.0),
                  N.math("SUBTRACT", 1.0, N.ao(0.8)))
    up = N.rng(N.nrm.outputs[2], 0.5, 0.95, 0.0, 0.6)
    g = N.math("MINIMUM", N.math("ADD", N.math("MULTIPLY", lime, 0.7), up), 1.0)
    north = N.rng(N.nrm.outputs[1], 0.15, 0.8, 0.0, 1.0)
    band = N.rng(z, 0.05, 1.1, 1.0, 0.0)
    pm = N.rng(N.r(N.tri("masks/m_plaque.png", 2.3, "Non-Color", off=(0.5, 0.2))), 0.05, 0.5, 0.0, 1.0)
    bb = N.math("MULTIPLY", N.math("MULTIPLY", north, band), pm)
    return N.rgb(r, g, bb)


def grime_ao(N):
    a = N.ao(1.5)
    return N.rgb(a, a, a)


def write_png(path, arr):
    """RGBA float 0…1 (строки снизу вверх, как пиксели Blender) → PNG 8 бит через изображение Blender."""
    h, w = arr.shape[:2]
    im = bpy.data.images.new(os.path.basename(path), w, h, alpha=True, float_buffer=False)
    im.colorspace_settings.name = "Non-Color"
    im.pixels.foreach_set(np.ascontiguousarray(arr, np.float32).ravel())
    im.filepath_raw = path
    im.file_format = "PNG"
    im.save()


def stage_bake():
    bpy.ops.wm.open_mainfile(filepath=GAME_BLEND)
    os.makedirs(OUT, exist_ok=True)
    # земля для AO у основания (в развёртку не печётся)
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, 0))
    ground = bpy.context.active_object
    for name, size in (("house7_lod0", 2048), ("house7_lod1", 1024)):
        ob = bpy.data.objects[name]
        for o in bpy.data.objects:
            if o.type == "MESH":
                o.hide_render = o not in (ob, ground)
        rgb = GL.new_image(name + "_grime_rgb", size)
        GL.bake_emission(ob, rgb, "UV2", grime_rgb, samples=16, margin=8)
        ao = GL.new_image(name + "_grime_ao", size)
        GL.bake_emission(ob, ao, "UV2", grime_ao, samples=16, margin=8)
        a = np.empty(size * size * 4, np.float32)
        rgb.pixels.foreach_get(a)
        b = np.empty(size * size * 4, np.float32)
        ao.pixels.foreach_get(b)
        a = a.reshape(size, size, 4)
        a[..., 3] = b.reshape(size, size, 4)[..., 0]
        # угловая клетка GL.NEUTRAL_UV (рамы, сталь, цепь, стекло): немного грязи, светлое AO
        k = int(size * 0.996)
        a[k:, k:] = (0.15, 0.08, 0.0, 0.85)
        write_png(OUT + "/%s_grime.png" % name, a)
        print("BAKED", name)
    bpy.data.objects.remove(ground)
    for o in bpy.data.objects:
        o.hide_render = False
    bpy.ops.wm.save_mainfile()


# ---------------------------------------------------------------- LOD2: цвет и нормаль с принятого вида
def stage_lod2():
    """Цвет и грубая нормаль LOD2 с LOD0 в материалах v01 (materials.py — те же узлы по мировым координатам, что у принятого
    вида; полный файл материалов с 640 экземплярами и шторами не помещается в память при запекании «выбранное → активное»)."""
    import materials as MT
    bpy.ops.wm.open_mainfile(filepath=GAME_BLEND)
    sc = bpy.context.scene
    low = bpy.data.objects["house7_lod2"]
    high = bpy.data.objects["house7_lod0"]
    for o in bpy.data.objects:
        o.hide_render = o not in (low, high)
    simple = {"window_glass": (0.035, 0.038, 0.042), "vestibule_glass": (0.02, 0.02, 0.022), "rail_glass": (0.25, 0.28, 0.28),
              "notice": (0.7, 0.68, 0.6), "lamp_dead": (0.4, 0.39, 0.36)}
    for slot in high.material_slots:
        n = slot.material.name.split(".")[0] if slot.material else ""
        if n in MT.MATS and n not in simple:
            slot.material = MT.get(n)
        else:
            m = bpy.data.materials.new("bake_" + n)
            m.use_nodes = True
            pr = m.node_tree.nodes.get("Principled BSDF")
            pr.inputs["Base Color"].default_value = simple.get(n, (0.3, 0.3, 0.3)) + (1.0,)
            pr.inputs["Roughness"].default_value = 0.6
            slot.material = m
    highs = [high]
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 4
    size = 2048
    out = {}
    for kind in ("DIFFUSE", "NORMAL"):
        im = bpy.data.images.new("lod2_" + kind, size, size, alpha=False, float_buffer=False)
        if kind == "NORMAL":
            im.colorspace_settings.name = "Non-Color"
        mat = low.material_slots[0].material.copy()
        low.material_slots[0].material = mat
        mat.use_nodes = True
        t = mat.node_tree.nodes.new("ShaderNodeTexImage")
        t.image = im
        mat.node_tree.nodes.active = t
        bpy.ops.object.select_all(action="DESELECT")
        for o in highs:
            o.select_set(True)
        low.select_set(True)
        bpy.context.view_layer.objects.active = low
        kw = dict(type=kind, use_selected_to_active=True, cage_extrusion=0.6, max_ray_distance=2.2, margin=8, use_clear=True)
        if kind == "DIFFUSE":
            kw["pass_filter"] = {"COLOR"}
        else:
            kw["normal_space"] = "TANGENT"
        bpy.ops.object.bake(**kw)
        a = np.empty(size * size * 4, np.float32)
        im.pixels.foreach_get(a)
        out[kind] = a.reshape(size, size, 4)
        print("LOD2 BAKED", kind)
    os.makedirs(OUT, exist_ok=True)
    alb = out["DIFFUSE"].copy()
    alb[..., 3] = 1.0
    im = bpy.data.images.new("lod2_albedo_out", size, size, alpha=False)
    im.pixels.foreach_set(alb.ravel())
    im.filepath_raw = OUT + "/house7_lod2_albedo.png"
    im.file_format = "PNG"
    im.save()
    nrm = out["NORMAL"].copy()
    nrm[..., 3] = 1.0
    write_png(OUT + "/house7_lod2_normal.png", nrm)


# ---------------------------------------------------------------- выгрузка
def gd(p):
    """Точка Blender → Godot (локальные оси дома после поворота на 180°: портал к −Z): (−x, z, y)."""
    return [round(-p[0], 4), round(p[2], 4), round(p[1], 4)]


def gd_box(x0, x1, y0, y1, z0, z1, name):
    a, b = gd((x0, y0, z0)), gd((x1, y1, z1))
    lo = [min(a[i], b[i]) for i in range(3)]
    hi = [max(a[i], b[i]) for i in range(3)]
    return dict(name=name, center=[round((lo[i] + hi[i]) / 2, 4) for i in range(3)], size=[round(hi[i] - lo[i], 4) for i in range(3)])


def collisions():
    HX, HY, top = H.HX, H.HY, H.H_TOP
    out = [gd_box(-HX, HX, -12.4, HY, 0.0, top, "body"),
           gd_box(-HX, HX, -HY, -12.4, HG, top, "front_upper"),
           gd_box(-HX, -4.0, -HY, -12.4, 0.0, HG, "front_left"),
           gd_box(2.0, HX, -HY, -12.4, 0.0, HG, "front_right"),
           gd_box(-4.0, 2.0, -HY, -12.4, 3.45, HG, "portal_head"),
           gd_box(-7.0, 7.0, -15.4, -HY, 3.5, 4.69, "canopy")]
    for sgn, nm in ((-1, "pylon_left"), (1, "pylon_right")):
        xs = sorted((sgn * 4.55, sgn * 6.9))
        out.append(gd_box(xs[0], xs[1], -15.0, -HY, 0.0, 1.8, nm + "_low"))
        xs = sorted((sgn * 5.3, sgn * 6.9))
        out.append(gd_box(xs[0], xs[1], -15.2, -HY, 1.8, 4.2, nm + "_high"))
    for k, (h, ya, yb) in enumerate(((1.35, -HY, -HY - 0.7), (0.90, -HY - 0.7, -HY - 1.4), (0.45, -HY - 1.4, -HY - 2.1))):
        out.append(gd_box(2.3, 5.7, yb, ya, 0.0, h, "bed_%d" % (k + 1)))
    # пилястры и угловые столбы (укрытия): по экземплярам сборки LOD0
    asm = bpy.data.collections["Сборка_LOD0"]
    k = 0
    for e in asm.objects:
        m = e.instance_collection.name if e.instance_collection else ""
        if m not in ("H_GroundPilaster", "H_GroundCornerPost"):
            continue
        loc = (0.0, 0.5, -0.48, 0.20) if m == "H_GroundPilaster" else (-0.48, 0.53, -0.48, 0.53)
        pts = [e.matrix_world @ Vector((x, y, 0.0)) for x in loc[:2] for y in loc[2:]]
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        out.append(gd_box(min(xs), max(xs), min(ys), max(ys), 0.0, HG, ("pilaster_%02d" if m == "H_GroundPilaster" else "corner_%02d") % k))
        k += 1
    for xc in (-7.5, 7.5):
        out.append(gd_box(xc - 3.12, xc + 3.12, -0.12, 5.12, H.H_ROOF, H.H_ROOF + 3.18, "roof_room_%d" % (1 if xc < 0 else 2)))
    return out


def stage_export():
    bpy.ops.wm.open_mainfile(filepath=GAME_BLEND)
    os.makedirs(OUT, exist_ok=True)
    rep = json.load(open(WORK + "/lods_report.json", encoding="utf-8"))
    R = Matrix.Rotation(math.pi, 4, "Z")
    for name in ("house7_lod0", "house7_lod1", "house7_lod2"):
        ob = bpy.data.objects[name]
        ob.data.transform(R)
        ob.data.update()
        if ob.data.color_attributes.get("Col"):
            ob.data.color_attributes.active_color = ob.data.color_attributes["Col"]
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        kw = dict(filepath=OUT + "/" + name + ".gltf", use_selection=True, export_format="GLTF_SEPARATE",
                  export_texcoords=True, export_normals=True, export_tangents=True, export_materials="EXPORT",
                  export_yup=True, export_apply=False, export_animations=False, export_extras=False)
        try:
            bpy.ops.export_scene.gltf(export_vertex_color="ACTIVE", **kw)
        except TypeError:
            bpy.ops.export_scene.gltf(export_colors=True, **kw)
        print("EXPORTED", name)
    lock = Vector(rep["lock_chain_blender"])
    door_lock = Vector((1.25 - 1.775, 13.0 - 0.150, 1.02))
    info = {
        "model": "дом 7 «Проспекта» — игровая версия (tools/prospekt_houses/house7_game.py)",
        "axes": "Godot, локально: Y вверх, портал и клумба к −Z (как подъезд flat_section.gd), лоджии без входа и служебная дверь к +Z; "
                "начало — центр пятна на земле; узел House7 в prospekt_study.tscn повёрнут на 180° — портал во двор",
        "footprint": [36.0, 26.0], "height": H.H_TOP, "height_antenna": H.H_ROOF + 6.2,
        "portal_out": H.PORTAL_OUT, "pilaster_out": 0.45,
        "lods": {k: rep[k] for k in ("house7_lod0", "house7_lod1", "house7_lod2")},
        "collisions": collisions(),
        # замки (модель assets/models/props/padlock_01: начало у основания корпуса, лицо к +Z, перемычка дужки на 0,114 м выше)
        "padlocks": [{"name": "padlock_chain", "bar": gd(lock), "yaw_deg": 180.0},
                     {"name": "padlock_door", "bar": gd(door_lock), "yaw_deg": 0.0}],
        "beds": [{"top": gd((4.0, (ya + yb) / 2, h - 0.05)), "size": [3.12, 0.42]} for (h, ya, yb) in
                 ((1.35, -13.0, -13.7), (0.90, -13.7, -14.4), (0.45, -14.4, -15.1))],
    }
    with open(OUT + "/house7.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    print("JSON ok")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    st = argv[0] if argv else "all"
    if st in ("lods", "all"):
        stage_lods()
    if st in ("bake", "all"):
        stage_bake()
    if st in ("lod2", "all"):
        stage_lod2()
    if st in ("export", "all"):
        stage_export()


if __name__ == "__main__":
    main()
