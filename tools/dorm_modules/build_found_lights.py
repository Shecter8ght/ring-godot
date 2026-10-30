"""Оставленный свет в общежитии (электричества нет — свет принесли и бросили люди): форма для просмотра владельцем
и выгрузка в стенд.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
      --python tools/dorm_modules/build_found_lights.py -- build "E:/Models Blender/ENVIRONMENT/RING_Dorm_FoundLights/models/RING_Dorm_FoundLights_v01.blend"
  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<тот же .blend>" --python-exit-code 1 \
      --python tools/dorm_modules/build_found_lights.py -- export

Предметы (размеры — типичных настоящих вещей, мм): фонарь ручной алюминиевый на 2×AA (152, головка Ø34),
налобник (корпус 58 × 36 × 30, резинка 25 петлёй), химсвет 15 см (Ø15, колпачок с ушком), кемпинговый фонарь
(Ø90, высота 160, проволочная ручка), свечи (окопная в банке Ø85 × 38, огарок в банке Ø73 × 110, огарок с натёками),
дорожная мигалка (корпус 130 × 75 × 100, линза Ø140 с кольцами Френеля). Корень предмета — точка опоры на полу,
+Y — куда светит (фонарь, налобник), Z — вверх. Материалы — по слотам; в стенде их ставит src/blockout/dorm_found_light.gd.
Выгрузка: assets/models/dorm/found_<вид>.glb (сетка на предмет) и found_lights.json — где свет (оси Godot).
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import mlib as L  # noqa: E402

V = Vector
TAU = 2.0 * math.pi
OUT_JSON = "E:/Games/RING-godot/assets/models/dorm/found_lights.json"

# имя файла в игре: (корень в .blend, точка света в осях предмета, направление луча или None — во все стороны)
ITEMS = {
    "found_flashlight": ("FL_фонарь_ручной", (0.0, 0.153, 0.0172), (0.0, 1.0, 0.0)),
    "found_headlamp": ("FL_налобник", (0.0, 0.034, 0.018), (0.0, 1.0, 0.0)),
    "found_chemlight": ("FL_химсвет", (0.0, 0.0, 0.03), None),
    "found_lantern": ("FL_фонарь_кемпинговый", (0.0, 0.0, 0.086), None),
    "found_candles": ("FL_свечи", (0.0, -0.05, 0.08), None),
    "found_beacon": ("FL_мигалка", (0.0, 0.0, 0.19), None),
}


# ---------------------------------------------------------------- построители

def lathe(bm, prof, segs=32, origin=(0, 0, 0), axis=(0, 0, 1), closed: bool = False) -> None:
    """Тело вращения: профиль (r, h) от оси до оси (r = 0 — вершина на оси), ось — axis через origin;
    closed — профиль-кольцо, не касающийся оси (последняя точка соединяется с первой)."""
    o, ax = V(origin), V(axis).normalized()
    ref = V((1, 0, 0)) if abs(ax.x) < 0.9 else V((0, 1, 0))
    a = (ref - ax * ref.dot(ax)).normalized()
    b = ax.cross(a)
    rings = []
    for r, h in prof:
        if r < 1e-7:
            rings.append([bm.verts.new(o + ax * h)])
        else:
            rings.append([bm.verts.new(o + ax * h + (a * math.cos(TAU * i / segs) + b * math.sin(TAU * i / segs)) * r)
                          for i in range(segs)])
    pairs = list(zip(rings, rings[1:])) + ([(rings[-1], rings[0])] if closed else [])
    for r0, r1 in pairs:
        if len(r0) == 1 and len(r1) == 1:
            continue
        for i in range(segs):
            j = (i + 1) % segs
            if len(r0) == 1:
                bm.faces.new((r0[0], r1[i], r1[j]))
            elif len(r1) == 1:
                bm.faces.new((r0[i], r0[j], r1[0]))
            else:
                bm.faces.new((r0[i], r0[j], r1[j], r1[i]))


def torus(bm, center, normal, radius: float, wire: float, segs=20, wsegs=8) -> None:
    """Кольцо из проволоки: окружность radius в плоскости с нормалью normal, сечение — круг wire."""
    c, n = V(center), V(normal).normalized()
    ref = V((1, 0, 0)) if abs(n.x) < 0.9 else V((0, 1, 0))
    a = (ref - n * ref.dot(n)).normalized()
    b = n.cross(a)
    rings = []
    for i in range(segs):
        t = TAU * i / segs
        d = a * math.cos(t) + b * math.sin(t)
        p = c + d * radius
        rings.append([bm.verts.new(p + (d * math.cos(TAU * k / wsegs) + n * math.sin(TAU * k / wsegs)) * wire)
                      for k in range(wsegs)])
    for i in range(segs):
        r0, r1 = rings[i], rings[(i + 1) % segs]
        for k in range(wsegs):
            m = (k + 1) % wsegs
            bm.faces.new((r0[k], r0[m], r1[m], r1[k]))


def circle(r: float, segs: int) -> list:
    return [(r * math.cos(TAU * i / segs), r * math.sin(TAU * i / segs)) for i in range(segs)]


def part(bm, name: str, coll, mat, parent, bevel: float = 0.0, segs: int = 2, angle: float = 40.0,
         smooth: float = 40.0) -> bpy.types.Object:
    return L.finish_bm(bm, name, coll, mat, parent, bevel=bevel, segs=segs, angle=angle, smooth_angle=smooth)


def multi(ob, mats: list, rule) -> None:
    """Добавить слоты и раздать грани по rule(центр, нормаль) → номер слота."""
    for m in mats[1:]:
        ob.data.materials.append(m)
    for p in ob.data.polygons:
        p.material_index = rule(p.center, p.normal)


# ---------------------------------------------------------------- материалы (нейтральные, для просмотра формы)

def mats() -> dict:
    def emit(name, color, strength):
        m = L.material(name, color, 0.4)
        bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        bsdf.inputs["Emission Color"].default_value = (color[0], color[1], color[2], 1.0)
        bsdf.inputs["Emission Strength"].default_value = strength
        return m
    return {
        "fl_body": L.material("Фонарь_корпус", (0.05, 0.05, 0.055), 0.35, 1.0),
        "fl_rubber": L.material("Фонарь_резина", (0.02, 0.02, 0.02), 0.85),
        "fl_reflector": L.material("Фонарь_отражатель", (0.85, 0.85, 0.85), 0.08, 1.0),
        "fl_glass": L.material("Фонарь_стекло", (0.9, 0.95, 1.0), 0.02, 0.0, 0.15),
        "fl_led": emit("Фонарь_светодиод", (1.0, 0.92, 0.78), 4.0),
        "hl_body": L.material("Налобник_корпус", (0.03, 0.03, 0.03), 0.55),
        "hl_strap": L.material("Налобник_ремень", (0.05, 0.08, 0.12), 0.9),
        "hl_buckle": L.material("Налобник_пряжка", (0.04, 0.04, 0.04), 0.5),
        "ch_tube": emit("Химсвет_трубка", (0.35, 1.0, 0.45), 2.0),
        "ch_cap": L.material("Химсвет_колпачок", (0.03, 0.03, 0.03), 0.5),
        "ln_body": L.material("Лампа_корпус", (0.08, 0.12, 0.08), 0.6),
        "ln_diffuser": emit("Лампа_рассеиватель", (1.0, 0.86, 0.66), 2.0),
        "ln_wire": L.material("Лампа_ручка", (0.6, 0.6, 0.6), 0.35, 1.0),
        "ln_rubber": L.material("Лампа_резина", (0.02, 0.02, 0.02), 0.85),
        "cn_tin": L.material("Банка_жесть", (0.62, 0.6, 0.56), 0.35, 1.0),
        "cn_wax": L.material("Свеча_воск", (0.85, 0.8, 0.66), 0.6),
        "cn_card": L.material("Картон", (0.36, 0.26, 0.16), 0.9),
        "cn_wick": L.material("Фитиль", (0.02, 0.02, 0.02), 0.9),
        "cn_flame": emit("Пламя", (1.0, 0.58, 0.22), 6.0),
        "bc_body": L.material("Мигалка_корпус", (0.85, 0.55, 0.05), 0.55),
        "bc_frame": L.material("Мигалка_оправа", (0.03, 0.03, 0.03), 0.6),
        "bc_lens": emit("Мигалка_линза", (1.0, 0.08, 0.03), 1.5),
    }


# ---------------------------------------------------------------- предметы

def flashlight(coll, m, at) -> bpy.types.Object:
    """Фонарь лежит на боку: ось вдоль +Y на высоте радиуса головки, хвост у y = 0."""
    r = L.root("FL_фонарь_ручной", coll, at)
    z0 = 0.0172
    prof = [(0.0, 0.003), (0.0075, 0.003), (0.0075, 0.0004), (0.0110, 0.0), (0.0124, 0.0012), (0.0125, 0.0200),
            (0.0119, 0.0210), (0.0119, 0.0225), (0.0122, 0.0232)]
    for h in (0.034, 0.040, 0.088, 0.094):  # пара мелких колец у хвоста и у шейки; накатка хвата — текстурой
        prof += [(0.0122, h), (0.0118, h + 0.0004), (0.0118, h + 0.0016), (0.0122, h + 0.002)]
    prof += [(0.0122, 0.1040), (0.0165, 0.1180), (0.0168, 0.1190)]
    for g in (0.1240, 0.1300, 0.1360):  # рёбра головки
        prof += [(0.0168, g), (0.0158, g + 0.0006), (0.0158, g + 0.0024), (0.0168, g + 0.003)]
    prof += [(0.0168, 0.1480), (0.0172, 0.1490), (0.0172, 0.1512), (0.0160, 0.1522), (0.0148, 0.1522),
             (0.0146, 0.1500), (0.0145, 0.1494), (0.0040, 0.1360), (0.0, 0.1360)]
    bm = bmesh.new()
    lathe(bm, prof, 40, (0, 0, z0), (0, 1, 0))
    body = part(bm, "фонарь_корпус", coll, m["fl_body"], r, bevel=0.0003, segs=1, angle=50)
    # отражатель — конус внутри головки
    multi(body, [m["fl_body"], m["fl_reflector"]],
          lambda c, n: 1 if c.y > 0.1355 and (V((c.x, c.z - z0)).length < 0.0146) and c.y < 0.1497 else 0)
    bm = bmesh.new()
    lathe(bm, [(0.0, -0.0025), (0.0045, -0.0022), (0.0064, -0.0010), (0.0068, 0.0), (0.0068, 0.0030), (0.0, 0.0030)],
          24, (0, 0, z0), (0, 1, 0))
    part(bm, "фонарь_кнопка", coll, m["fl_rubber"], r)
    bm = bmesh.new()
    lathe(bm, [(0.0, 0.1495), (0.0146, 0.1495), (0.0146, 0.1507), (0.0, 0.1507)], 40, (0, 0, z0), (0, 1, 0))
    part(bm, "фонарь_стекло", coll, m["fl_glass"], r)
    bm = bmesh.new()
    lathe(bm, [(0.0, 0.1358), (0.0026, 0.1358), (0.0026, 0.1368), (0.0016, 0.1376), (0.0, 0.1378)], 16, (0, 0, z0), (0, 1, 0))
    part(bm, "фонарь_светодиод", coll, m["fl_led"], r)
    return r


def headlamp(coll, m, at) -> bpy.types.Object:
    """Налобник на столешнице: корпус светит по +Y, резинка петлёй на ребре позади."""
    r = L.root("FL_налобник", coll, at)
    bm = bmesh.new()
    L.bm_prism(bm, L.rrect(0.058, 0.036, 0.010, 4), (0, -0.006, 0.018), (1, 0, 0), (0, 0, 1), (0, 0.030, 0))
    part(bm, "налобник_корпус", coll, m["hl_body"], r, bevel=0.003, segs=3, angle=30)
    bm = bmesh.new()  # оправа линзы — кольцо на лицевой стороне
    lathe(bm, [(0.0125, 0.0236), (0.0150, 0.0236), (0.0150, 0.0300), (0.0142, 0.0320), (0.0125, 0.0320)], 32,
          (0.0, 0.0, 0.018), (0, 1, 0), closed=True)
    part(bm, "налобник_оправа", coll, m["hl_body"], r, bevel=0.0003, segs=1)
    bm = bmesh.new()  # отражатель — чашка внутри оправы
    lathe(bm, [(0.0, 0.0236), (0.0124, 0.0236), (0.0124, 0.0300), (0.0040, 0.0242), (0.0, 0.0242)], 32,
          (0.0, 0.0, 0.018), (0, 1, 0))
    part(bm, "налобник_отражатель", coll, m["fl_reflector"], r)
    bm = bmesh.new()
    lathe(bm, [(0.0, 0.0296), (0.0124, 0.0296), (0.0124, 0.0304), (0.0, 0.0304)], 32, (0, 0, 0.018), (0, 1, 0))
    part(bm, "налобник_стекло", coll, m["fl_glass"], r)
    bm = bmesh.new()
    lathe(bm, [(0.0, 0.0242), (0.0022, 0.0242), (0.0022, 0.0250), (0.0012, 0.0256), (0.0, 0.0257)], 12, (0, 0, 0.018), (0, 1, 0))
    part(bm, "налобник_светодиод", coll, m["fl_led"], r)
    bm = bmesh.new()  # кронштейн с шарниром и прорезями под резинку
    L.bm_prism(bm, L.rrect(0.046, 0.032, 0.006, 3), (0, -0.0105, 0.018), (1, 0, 0), (0, 0, 1), (0, 0.0035, 0))
    for sx in (-0.016, 0.016):
        L.bm_cyl(bm, (sx - 0.006, -0.0075, 0.030), (sx + 0.006, -0.0075, 0.030), 0.0035, 12)
    part(bm, "налобник_кронштейн", coll, m["hl_buckle"], r, bevel=0.0008, segs=2)
    # резинка: петля на ребре, проходит за кронштейном; на дальней стороне — пряжка
    pts = []
    a_x, b_y, cy = 0.085, 0.072, -0.0125 - 0.072
    for i in range(48):
        t = TAU * i / 48 + math.pi / 2
        wob = 1.0 + 0.04 * math.sin(3 * t) + 0.025 * math.cos(5 * t)
        pts.append((a_x * math.cos(t) * wob, cy + b_y * math.sin(t) * wob, 0.0))
    bm = bmesh.new()
    L.bm_sweep(bm, pts, [(-0.00075, 0.0005), (0.00075, 0.0005), (0.00075, 0.0255), (-0.00075, 0.0255)], closed=True)
    part(bm, "налобник_резинка", coll, m["hl_strap"], r, smooth=60)
    bm = bmesh.new()
    L.bm_prism(bm, L.rrect(0.034, 0.030, 0.004, 2), (0, cy - b_y - 0.004, 0.0155), (1, 0, 0), (0, 0, 1), (0, 0.008, 0))
    part(bm, "налобник_пряжка", coll, m["hl_buckle"], r, bevel=0.0006)
    return r


def chemlight(coll, m, at) -> bpy.types.Object:
    """Химсвет лежит вдоль X; колпачок с ушком на +X."""
    r = L.root("FL_химсвет", coll, at)
    z = 0.0082
    bm = bmesh.new()
    lathe(bm, [(0.0, -0.0750), (0.0045, -0.0746), (0.0068, -0.0734), (0.0075, -0.0715), (0.0075, 0.0600), (0.0, 0.0600)],
          20, (0, 0, z), (1, 0, 0))
    part(bm, "химсвет_трубка", coll, m["ch_tube"], r, smooth=50)
    bm = bmesh.new()
    lathe(bm, [(0.0, 0.0570), (0.0081, 0.0570), (0.0082, 0.0590), (0.0082, 0.0720), (0.0072, 0.0748), (0.0045, 0.0758),
               (0.0, 0.0760)], 20, (0, 0, z), (1, 0, 0))
    for k in range(5):  # рёбра колпачка
        h = 0.0605 + k * 0.0025
        L.bm_cyl(bm, (h, 0, z), (h + 0.0008, 0, z), 0.0084, 20)
    part(bm, "химсвет_колпачок", coll, m["ch_cap"], r, bevel=0.0003, segs=1)
    bm = bmesh.new()
    torus(bm, (0.0815, 0, z), (0, 1, 0), 0.0046, 0.0011, 18, 6)
    part(bm, "химсвет_ушко", coll, m["ch_cap"], r)
    return r


def lantern(coll, m, at) -> bpy.types.Object:
    r = L.root("FL_фонарь_кемпинговый", coll, at)
    bm = bmesh.new()
    lathe(bm, [(0.0, 0.004), (0.041, 0.004), (0.044, 0.006), (0.045, 0.010), (0.045, 0.034), (0.0435, 0.0385),
               (0.0400, 0.0410), (0.0360, 0.0410), (0.0360, 0.0440), (0.0, 0.0440)], 40)
    L.bm_box(bm, (-0.012, -0.0465, 0.016), (0.012, -0.044, 0.028))  # защёлка отсека батареек
    part(bm, "лампа_основание", coll, m["ln_body"], r, bevel=0.0012, segs=2)
    bm = bmesh.new()
    lathe(bm, [(0.0, 0.0), (0.040, 0.0), (0.0425, 0.0015), (0.0425, 0.0045), (0.0, 0.0045)], 40)
    part(bm, "лампа_ножка", coll, m["ln_rubber"], r)
    bm = bmesh.new()
    prof = [(0.0, 0.042)]
    for k in range(11):
        h = 0.042 + k * 0.009
        prof.append((0.0355 + 0.0025 * math.sin(math.pi * k / 10), h))
    prof.append((0.0, 0.132))
    lathe(bm, prof, 40)
    part(bm, "лампа_рассеиватель", coll, m["ln_diffuser"], r, smooth=60)
    bm = bmesh.new()
    lathe(bm, [(0.0, 0.1300), (0.0380, 0.1300), (0.0430, 0.1330), (0.0430, 0.1500), (0.0400, 0.1560), (0.0120, 0.1580),
               (0.0, 0.1580)], 40)
    for sx in (-0.0445, 0.0445):  # проушины ручки
        L.bm_box(bm, (sx - 0.003, -0.005, 0.138), (sx + 0.003, 0.005, 0.150))
    part(bm, "лампа_крышка", coll, m["ln_body"], r, bevel=0.0012, segs=2)
    bm = bmesh.new()
    lathe(bm, [(0.0, 0.1575), (0.0090, 0.1575), (0.0090, 0.1610), (0.0080, 0.1625), (0.0, 0.1628)], 24)
    part(bm, "лампа_кнопка", coll, m["ln_rubber"], r)
    # проволочная ручка: стоит дугой над крышкой
    pts = [(-0.0475, 0.0, 0.144), (-0.0475, 0.0, 0.170)]
    for k in range(1, 12):
        t = math.pi * k / 12
        pts.append((-0.0475 * math.cos(t), 0.0, 0.170 + 0.022 * math.sin(t)))
    pts += [(0.0475, 0.0, 0.170), (0.0475, 0.0, 0.144)]
    bm = bmesh.new()
    L.bm_sweep(bm, pts, circle(0.0016, 8), up=(0, 1, 0))
    part(bm, "лампа_ручка", coll, m["ln_wire"], r, smooth=60)
    return r


def flame(bm, at, s: float = 1.0) -> None:
    x, y, z = at
    lathe(bm, [(0.0, 0.0), (0.0030 * s, 0.0030 * s), (0.0040 * s, 0.0075 * s), (0.0032 * s, 0.0125 * s),
               (0.0016 * s, 0.0180 * s), (0.0, 0.0225 * s)], 12, (x, y, z))


def candles(coll, m, at) -> bpy.types.Object:
    """Три огня на подоконнике: окопная свеча в низкой банке, огарок в высокой, огарок в натёках прямо на доске."""
    r = L.root("FL_свечи", coll, at)
    ax, bx, cx = -0.125, 0.0, 0.115
    tin, wax, card, wick, fire = (bmesh.new() for _ in range(5))
    # окопная: банка Ø85 × 38 с закаткой, внутри воск и свёрнутый картон
    lathe(tin, [(0.0, 0.0), (0.0412, 0.0), (0.0425, 0.0015), (0.0425, 0.0360), (0.0433, 0.0372), (0.0433, 0.0386),
                (0.0418, 0.0390), (0.0412, 0.0380), (0.0412, 0.0300), (0.0, 0.0300)], 40, (ax, 0, 0))
    lathe(wax, [(0.0, 0.0298), (0.0411, 0.0298), (0.0411, 0.0310), (0.0, 0.0310)], 40, (ax, 0, 0))
    spiral = []
    for k in range(90):
        t = 2.6 * TAU * k / 89
        rr = 0.005 + 0.031 * k / 89
        spiral.append((ax + rr * math.cos(t), rr * math.sin(t), 0.031))
    L.bm_sweep(card, spiral, [(-0.0006, 0.0), (0.0006, 0.0), (0.0006, 0.0035), (-0.0006, 0.0035)], up=(0, 0, 1))
    for k in (40, 72):
        x, y, _ = spiral[k]
        flame(fire, (x, y, 0.0345), 1.25)
    # огарок в высокой банке Ø73 × 110: свет вверх и через край
    lathe(tin, [(0.0, 0.0), (0.0355, 0.0), (0.0367, 0.0015), (0.0367, 0.1080), (0.0374, 0.1092), (0.0374, 0.1104),
                (0.0360, 0.1108), (0.0355, 0.1098), (0.0355, 0.0020), (0.0, 0.0020)], 40, (bx, 0, 0))
    for k in range(5):  # рёбра жёсткости банки
        h = 0.022 + k * 0.017
        L.bm_cyl(tin, (bx, 0, h), (bx, 0, h + 0.003), 0.0369, 40)
    lathe(wax, [(0.0, 0.0020), (0.0140, 0.0020), (0.0140, 0.0480), (0.0125, 0.0505), (0.0040, 0.0510), (0.0, 0.0500)],
          24, (bx, 0, 0))
    L.bm_cyl(wick, (bx, 0, 0.050), (bx + 0.0008, 0, 0.058), 0.0007, 6)
    flame(fire, (bx + 0.0008, 0, 0.0585), 1.0)
    # огарок прямо на подоконнике: натёки и лужица
    lathe(wax, [(0.0, 0.0010), (0.0120, 0.0010), (0.0120, 0.0420), (0.0105, 0.0448), (0.0040, 0.0455), (0.0, 0.0445)],
          24, (cx, 0, 0))
    pud = [(cx + (0.030 + 0.006 * math.sin(3 * t) + 0.004 * math.cos(7 * t)) * math.cos(t),
            (0.026 + 0.005 * math.cos(4 * t)) * math.sin(t)) for t in [TAU * i / 32 for i in range(32)]]
    L.bm_prism(wax, pud, (0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 0.0025))
    for k, (dz, ang, sz) in enumerate(((0.030, 0.4, 1.0), (0.018, 2.1, 1.3), (0.036, 4.0, 0.8), (0.010, 5.2, 1.1))):
        d = V((math.cos(ang), math.sin(ang), 0))
        c = V((cx, 0, dz)) + d * 0.0118
        bmesh.ops.create_uvsphere(wax, u_segments=8, v_segments=6, radius=0.0035 * sz,
                                  matrix=Matrix.Translation(c) @ Matrix.Diagonal((0.8, 0.8, 2.2, 1.0)))
    L.bm_cyl(wick, (cx, 0, 0.0445), (cx - 0.0010, 0, 0.0525), 0.0007, 6)
    flame(fire, (cx - 0.0010, 0, 0.0525), 1.1)
    part(tin, "свечи_банки", coll, m["cn_tin"], r, bevel=0.0004, segs=1)
    part(wax, "свечи_воск", coll, m["cn_wax"], r, smooth=50)
    part(card, "свечи_картон", coll, m["cn_card"], r, smooth=60)
    part(wick, "свечи_фитили", coll, m["cn_wick"], r)
    part(fire, "свечи_пламя", coll, m["cn_flame"], r, smooth=80)
    return r


def beacon(coll, m, at) -> bpy.types.Object:
    """Дорожная мигалка: корпус с батареями и ручкой, линза смотрит по ±Y."""
    r = L.root("FL_мигалка", coll, at)
    bm = bmesh.new()
    L.bm_prism(bm, L.rrect(0.130, 0.100, 0.012, 3), (0, -0.0375, 0.050), (1, 0, 0), (0, 0, 1), (0, 0.075, 0))
    part(bm, "мигалка_корпус", coll, m["bc_body"], r, bevel=0.004, segs=3, angle=30)
    bm = bmesh.new()  # ручка-скоба сверху и стойка линзы
    L.bm_sweep(bm, [(-0.050, 0, 0.098), (-0.050, 0, 0.112), (-0.030, 0, 0.118), (0.030, 0, 0.118), (0.050, 0, 0.112),
                    (0.050, 0, 0.098)], L.rrect(0.012, 0.010, 0.004, 2), up=(0, 1, 0))
    L.bm_box(bm, (-0.012, -0.012, 0.098), (0.012, 0.012, 0.122))
    part(bm, "мигалка_ручка", coll, m["bc_frame"], r, bevel=0.0015, segs=2)
    zc = 0.190
    bm = bmesh.new()  # оправа линзы: кольцо вокруг оси Y
    lathe(bm, [(0.0610, -0.0170), (0.0700, -0.0170), (0.0720, -0.0150), (0.0720, 0.0150), (0.0700, 0.0170),
               (0.0610, 0.0170), (0.0610, 0.0120), (0.0660, 0.0120), (0.0660, -0.0120), (0.0610, -0.0120)],
          48, (0, 0, zc), (0, 1, 0), closed=True)
    part(bm, "мигалка_оправа", coll, m["bc_frame"], r, bevel=0.001, segs=1)
    bm = bmesh.new()  # линза с кольцами Френеля с обеих сторон
    prof = [(0.0, -0.0105)]
    rr = 0.006
    while rr < 0.060:
        prof += [(rr, -0.0105), (rr + 0.0001, -0.0115)]
        rr += 0.006
    prof += [(0.0625, -0.0115), (0.0625, 0.0115)]
    rr = 0.060
    while rr > 0.006:
        prof += [(rr + 0.0001, 0.0115), (rr, 0.0105)]
        rr -= 0.006
    prof += [(0.0, 0.0105)]
    lathe(bm, prof, 48, (0, 0, zc), (0, 1, 0))
    part(bm, "мигалка_линза", coll, m["bc_lens"], r, smooth=10)
    return r


# ---------------------------------------------------------------- сборка файла и просмотр

def studio(coll) -> None:
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.get("Студия") or bpy.data.worlds.new("Студия")
    try:
        world.use_nodes = True
    except AttributeError:
        pass
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.32, 0.34, 0.37, 1.0)
    bg.inputs[1].default_value = 0.4
    sc.world = world
    bm = bmesh.new()
    L.bm_box(bm, (-0.45, -0.35, -0.02), (0.85, 0.35, 0.0))
    L.finish_bm(bm, "студия_пол", coll, L.material("Студия_бетон", (0.22, 0.21, 0.2), 0.9))
    ld = bpy.data.lights.new("Студия_свет", "AREA")
    ld.energy = 60
    ld.size = 1.2
    lo = bpy.data.objects.new("Студия_свет", ld)
    lo.location = (0.2, -0.6, 0.8)
    lo.rotation_euler = (math.radians(50), 0, 0)
    coll.objects.link(lo)
    cd = bpy.data.cameras.new("Камера_обзор")
    cd.lens = 32
    co = bpy.data.objects.new("Камера_обзор", cd)
    co.location = (0.24, -1.15, 0.55)
    co.rotation_euler = (V((0.24, 0.0, 0.06)) - V(co.location)).to_track_quat("-Z", "Y").to_euler()
    coll.objects.link(co)
    sc.camera = co


def build(out: str) -> None:
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    top = L.collection("Свет_оставленный_v01")
    m = mats()
    makers = [(flashlight, (-0.32, 0.0, 0.0)), (headlamp, (-0.12, 0.12, 0.0)), (chemlight, (0.08, -0.12, 0.0)),
              (lantern, (0.22, 0.05, 0.0)), (candles, (0.48, -0.05, 0.0)), (beacon, (0.75, 0.05, 0.0))]
    for fn, at in makers:
        c = L.collection(fn.__name__, top)
        fn(c, m, at)
    studio(L.collection("Студия"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("saved", out)


def export() -> None:
    import godot_export as G
    meta = {}
    for name, (root_name, light, beam) in ITEMS.items():
        root = bpy.data.objects[root_name]
        G.export(name, root, [o for o in root.children_recursive if o.type == "MESH"])
        # оси Godot: (x, z, −y)
        meta[name] = {"light": [light[0], light[2], -light[1]],
                      "beam": None if beam is None else [beam[0], beam[2], -beam[1]]}
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print("meta", OUT_JSON)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if argv and argv[0] == "build":
        build(argv[1])
    elif argv and argv[0] == "export":
        export()
    else:
        raise SystemExit("build <out.blend> | export")
