"""Сигнальный пистолет (ракетница) по образцу СП-81, 26 мм, и два патрона — модель Claude.

Основа формы — фото владельца (_asset_src/flare_gun_claude/refs: 01, 03, 04, 05 — СП-81; 03, 06 — патроны).
Размеры сняты с фото 03 (вид сбоку) от известной длины СП-81 175 мм: ствол Ø32 × 125, канал 26.7.

Что строит:
  FlareGun_Claude — рама с казёнником (одна деталь), ствол на оси (переламывается), спуск, защёлка ствола,
                    щёчки рукоятки (пластик на стальной раме), винты щёчек, оси, антабка; метки
                    Muzzle (срез) и Chamber (донце патрона). Курок у СП-81 внутренний — снаружи его нет.
  Flare_Red_Claude   — осветительный патрон: картонная гильза, металлическое донце, красные крышка и пояс,
                       на крышке один бугорок (на ощупь).
  Flare_Green_Claude — патрон вызова груза: то же, зелёные крышка и пояс, два бугорка.

Материалы раздельные (под текстурирование UCUPaint): FlareGun_Body_Metal — рама и ствол (будет красная
матовая краска с потёртостями до металла), FlareGun_Small_Steel — мелкие стальные детали,
FlareGun_Grip_Plastic — щёчки; у патронов — металл донца, картон, красная / зелёная маркировка.
Развёртка — своя на каждый материал (все детали материала в одном поле 0–1).

Оси сцены как у ВЕРАСа: дуло по −Y, верх +Z, +X — левая сторона стрелка; начало — середина рукоятки.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_flare_gun_claude.py
→ _asset_src/flare_gun_claude/FlareGun_SP81_Claude_v01.blend (правится: фаски модификаторами),
  …_v01_game.blend (модификаторы применены, развёртка), Просмотр/*.png, asset-audit.json;
  assets/models/weapons/flare_gun_claude/{flare_gun_claude,flare_red_claude,flare_green_claude}.glb
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "_asset_src/flare_gun_claude"
OUT = ROOT / "assets/models/weapons/flare_gun_claude"
MM = 0.001
# середина рукоятки (в осях чертежа: u — вперёд от казённого среза, v — вверх от оси ствола) — начало сцены
U0, V0 = -22.0, -72.0
BORE_R, BARREL_R, BARREL_L = 13.35, 16.0, 125.0
HINGE = (74.0, -29.0)
ARM_TOP = -18.2
SEG = 48


def P(u: float, v: float, x: float = 0.0) -> Vector:
    """Точка чертежа (мм) → сцена (м): дуло по −Y."""
    return Vector((x * MM, -(u - U0) * MM, (v - V0) * MM))


def fillet(pts: list) -> list:
    """Контур [(a, b, радиус скругления угла)…] → ломаная [(a, b)…] со скруглёнными углами."""
    out: list = []
    n = len(pts)
    for i in range(n):
        p0 = Vector(pts[i - 1][:2])
        p1 = Vector(pts[i][:2])
        p2 = Vector(pts[(i + 1) % n][:2])
        r = pts[i][2] if len(pts[i]) > 2 else 0.0
        d0, d1 = p0 - p1, p2 - p1
        if r <= 0.0 or d0.length < 1e-6 or d1.length < 1e-6:
            out.append((p1.x, p1.y))
            continue
        ang = d0.angle(d1)
        if ang > math.pi - 0.02:
            out.append((p1.x, p1.y))
            continue
        t = min(r / math.tan(ang / 2.0), 0.45 * d0.length, 0.45 * d1.length)
        rr = t * math.tan(ang / 2.0)
        a = p1 + d0.normalized() * t
        b = p1 + d1.normalized() * t
        c = p1 + (d0.normalized() + d1.normalized()).normalized() * (rr / math.sin(ang / 2.0))
        a0 = math.atan2(a.y - c.y, a.x - c.x)
        sweep = math.atan2(b.y - c.y, b.x - c.x) - a0
        while sweep > math.pi:
            sweep -= math.tau
        while sweep < -math.pi:
            sweep += math.tau
        steps = max(2, int(abs(sweep) / math.radians(13)) + 1)
        for k in range(steps + 1):
            w = a0 + sweep * k / steps
            out.append((c.x + rr * math.cos(w), c.y + rr * math.sin(w)))
    return out


def arc(cu: float, cv: float, r: float, a0: float, a1: float, n: int) -> list:
    return [(cu + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cv + r * math.sin(math.radians(a0 + (a1 - a0) * i / n)), 0.0)
            for i in range(n + 1)]


def new_object(name: str, bm: bmesh.types.BMesh, materials, origin: Vector | None = None, parent=None):
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    for m in (materials if isinstance(materials, (list, tuple)) else [materials]):
        me.materials.append(m)
    for poly in me.polygons:
        poly.use_smooth = True
    if origin is not None:
        me.transform(Matrix.Translation(-origin))
        ob.location = origin
    if parent is not None:
        ob.parent = parent
    return ob


def slab(bm: bmesh.types.BMesh, base: list, push: Vector) -> None:
    """Пластина: контур из точек сцены, вытянутый на push."""
    a = [bm.verts.new(p) for p in base]
    b = [bm.verts.new(p + push) for p in base]
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    n = len(base)
    for i in range(n):
        bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))


def prism(bm: bmesh.types.BMesh, pts: list, x0: float, x1: float) -> None:
    """Пластина по контуру вида сбоку pts [(u, v)…] толщиной от x0 до x1 (мм)."""
    slab(bm, [P(p[0], p[1], x0) for p in pts], Vector(((x1 - x0) * MM, 0, 0)))


def lathe(bm: bmesh.types.BMesh, profile: list, closed: bool = True, seg: int = SEG, axis_v: float = 0.0, axis_x: float = 0.0,
          caps: tuple = (False, False), mats: list | None = None) -> None:
    """Тело вращения вокруг оси, параллельной стволу: profile [(u, r)…] (мм). mats — материал каждого пояса."""
    rings = []
    for u, r in profile:
        rings.append([bm.verts.new(P(u, axis_v + r * math.sin(math.tau * k / seg), axis_x + r * math.cos(math.tau * k / seg))) for k in range(seg)])
    count = len(rings) if closed else len(rings) - 1
    for i in range(count):
        r0, r1 = rings[i], rings[(i + 1) % len(rings)]
        for k in range(seg):
            f = bm.faces.new((r0[k], r0[(k + 1) % seg], r1[(k + 1) % seg], r1[k]))
            if mats:
                f.material_index = mats[i]
    if caps[0]:
        f = bm.faces.new(rings[0])
        f.material_index = mats[0] if mats else 0
    if caps[1]:
        f = bm.faces.new(rings[-1])
        f.material_index = mats[-1] if mats else 0


def cyl_x(bm: bmesh.types.BMesh, u: float, v: float, r: float, x0: float, x1: float, seg: int = 24) -> None:
    """Цилиндр поперёк оружия (вдоль X) с торцами."""
    prism(bm, [(u + r * math.cos(math.tau * k / seg), v + r * math.sin(math.tau * k / seg)) for k in range(seg)], x0, x1)


def material(name: str, color: tuple, metallic: float, roughness: float):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = roughness
    return m


def bevel(ob, width_mm: float, segments: int = 2, angle: float = 35.0, harden: bool = True) -> None:
    mod = ob.modifiers.new("Фаска", "BEVEL")
    mod.width = width_mm * MM
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(angle)
    mod.harden_normals = harden
    if harden:
        wn = ob.modifiers.new("Нормали", "WEIGHTED_NORMAL")
        wn.keep_sharp = True


def boolean(target, tool, operation: str) -> None:
    mod = target.modifiers.new("Булева", "BOOLEAN")
    mod.operation = operation
    mod.object = tool
    mod.solver = "EXACT"
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(tool, do_unlink=True)
    for poly in target.data.polygons:
        poly.use_smooth = True


def temp(bm: bmesh.types.BMesh):
    return new_object("_tmp", bm, M_BODY)


# ---------------------------------------------------------------- сцена

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 1.0

M_BODY = material("FlareGun_Body_Metal", (0.30, 0.31, 0.33), 1.0, 0.45)
M_STEEL = material("FlareGun_Small_Steel", (0.07, 0.075, 0.085), 1.0, 0.4)
M_GRIP = material("FlareGun_Grip_Plastic", (0.17, 0.06, 0.04), 0.0, 0.5)
M_HEAD = material("Flare_Case_Metal", (0.72, 0.72, 0.70), 1.0, 0.35)
M_PAPER = material("Flare_Case_Paper", (0.72, 0.56, 0.30), 0.0, 0.85)
M_RED = material("Flare_Mark_Red", (0.70, 0.03, 0.03), 0.0, 0.5)
M_GREEN = material("Flare_Mark_Green", (0.03, 0.38, 0.09), 0.0, 0.5)

gun = bpy.data.objects.new("FlareGun_Claude", None)
scene.collection.objects.link(gun)
gun.empty_display_size = 0.02

# ---- рама: стальная пластина (рукоять + «рука» под стволом до оси) с пазами под выступ ствола и его ушко
bm = bmesh.new()
plate = [(-38.0, -18.0, 0.0), (68.0, ARM_TOP, 0.0)] + arc(HINGE[0], HINGE[1], 12.0, 105, -100, 16)
plate += [(58.0, -38.0, 8.0), (28.0, -36.5, 5.0), (22.0, -38.5, 4.0), (13.5, -72.0, 30.0), (1.0, -106.0, 20.0), (-4.0, -115.5, 5.0),
          (-40.0, -116.0, 9.0), (-52.0, -102.0, 12.0), (-47.5, -45.0, 40.0)]
prism(bm, fillet(plate), -5.0, 5.0)
frame = new_object("Frame", bm, M_BODY, parent=gun)
# ребро вдоль «руки» (на фото — длинная выпуклая полка под стволом)
bm = bmesh.new()
prism(bm, fillet([(-24.0, -24.2, 1.2), (58.0, -24.2, 1.4), (58.0, -27.6, 1.4), (-24.0, -27.6, 1.2)]), -6.3, 6.3)
boolean(frame, temp(bm), "UNION")

# ---- казённик: пересечение трёх видов (сбоку, спереди, сверху) — скруглённый щит шириной со ствол
bm = bmesh.new()
side = [(0.0, 16.6, 1.5), (-17.0, 12.0, 14.0), (-35.0, -10.0, 30.0), (-43.0, -22.0, 20.0), (-44.0, -33.5, 9.0), (-30.0, -37.0, 0.0), (5.0, -37.0, 0.0),
        (5.0, -17.0, 2.0), (0.0, -17.0, 0.0)]
prism(bm, fillet(side), -20.0, 20.0)
block = new_object("Frame_Breech", bm, M_BODY, parent=gun)
bm = bmesh.new()
front = [(16.6 * math.cos(math.radians(a)), 16.6 * math.sin(math.radians(a)), 0.0) for a in range(0, 181, 6)]
front += [(-16.6, -10.0, 10.0), (-12.0, -31.0, 8.0), (-12.0, -42.0, 0.0), (12.0, -42.0, 0.0), (12.0, -31.0, 8.0), (16.6, -10.0, 10.0)]
slab(bm, [P(-70.0, v, x) for x, v in fillet(front)], P(8.0, 0.0) - P(-70.0, 0.0))
boolean(block, temp(bm), "INTERSECT")
bm = bmesh.new()
top = [(8.0, 16.7, 0.0), (8.0, -16.7, 0.0), (-20.0, -16.7, 14.0), (-41.0, -10.0, 14.0), (-49.5, -5.0, 4.0), (-49.5, 5.0, 4.0),
       (-41.0, 10.0, 14.0), (-20.0, 16.7, 14.0)]
slab(bm, [P(u, -45.0, x) for u, x in fillet(top)], P(0.0, 25.0) - P(0.0, -45.0))
boolean(block, temp(bm), "INTERSECT")
# ушко под шнур на «горбе»
bm = bmesh.new()
cyl_x(bm, -21.0, 11.2, 5.4, -3.0, 3.0, 28)
boolean(block, temp(bm), "UNION")
bm = bmesh.new()
cyl_x(bm, -21.0, 12.2, 2.3, -30.0, 30.0, 20)
boolean(block, temp(bm), "DIFFERENCE")
boolean(frame, block, "UNION")
# пазы: под запорный выступ ствола и под ушко оси
bm = bmesh.new()
prism(bm, [(1.5, -30.0), (34.0, -30.0), (34.0, -10.0), (1.5, -10.0)], -3.5, 3.5)
prism(bm, [(59.0, -50.0), (90.0, -50.0), (90.0, -10.0), (59.0, -10.0)], -2.6, 2.6)
boolean(frame, temp(bm), "DIFFERENCE")
bevel(frame, 1.0, 2, 48.0, False)

# ---- ствол: труба с поясом у казны, расточка под закраину, снизу — планка, запорный выступ и ушко оси
bm = bmesh.new()
lathe(bm, [(1.7, BORE_R), (1.7, 14.6), (0.0, 14.6), (0.0, BARREL_R + 0.3), (0.8, BARREL_R + 1.1), (7.2, BARREL_R + 1.1), (8.0, BARREL_R + 0.3),
           (8.4, BARREL_R), (BARREL_L - 1.0, BARREL_R), (BARREL_L, BARREL_R - 1.0), (BARREL_L, BORE_R + 0.6), (BARREL_L - 0.6, BORE_R)])
prism(bm, [(3.0, -14.5), (84.0, -14.5), (84.0, ARM_TOP + 0.15), (3.0, ARM_TOP + 0.15)], -5.0, 5.0)
prism(bm, fillet([(4.0, -15.0, 0.0), (31.5, -15.0, 0.0), (31.5, -27.5, 2.5), (4.0, -27.5, 2.5)]), -3.0, 3.0)
prism(bm, fillet([(61.0, -15.0, 0.0), (83.0, -15.0, 0.0)] + arc(HINGE[0], HINGE[1], 9.0, 0, -180, 12)), -2.2, 2.2)
barrel = new_object("Barrel", bm, M_BODY, origin=P(*HINGE), parent=gun)
bevel(barrel, 0.5)
# окно защёлки в запорном выступе (на фото 04 — отверстие)
bm = bmesh.new()
prism(bm, fillet([(13.0, -19.5, 1.6), (22.0, -19.5, 1.6), (22.0, -24.0, 1.6), (13.0, -24.0, 1.6)]), -8.0, 8.0)
bpy.context.view_layer.update()
boolean(barrel, temp(bm), "DIFFERENCE")

# ---- мелкие стальные детали
bm = bmesh.new()
cyl_x(bm, HINGE[0], HINGE[1], 2.6, -6.0, 6.0)
cyl_x(bm, HINGE[0], HINGE[1], 4.4, 4.9, 6.4)
cyl_x(bm, HINGE[0], HINGE[1], 4.4, -6.4, -4.9)
cyl_x(bm, 25.0, -33.0, 1.5, -5.5, 5.5)       # ось спуска
cyl_x(bm, 40.0, -33.5, 1.5, -5.5, 5.5)       # ось защёлки
pins = new_object("Pins", bm, M_STEEL, parent=gun)
bevel(pins, 0.5, 2)

bm = bmesh.new()
prism(bm, fillet([(21.5, -31.0, 1.0), (27.5, -31.0, 1.0), (27.8, -50.0, 20.0), (29.0, -63.0, 12.0), (32.0, -70.5, 1.2), (31.0, -73.5, 1.2),
                  (25.0, -73.5, 2.5), (23.2, -62.0, 14.0), (22.0, -48.0, 20.0)]), -3.2, 3.2)
trigger = new_object("Trigger", bm, M_STEEL, origin=P(25.0, -33.0), parent=gun)
bevel(trigger, 1.0, 2)

bm = bmesh.new()
prism(bm, [(34.5, -31.0), (49.0, -31.0), (50.0, -40.0), (48.2, -42.2), (46.4, -40.6), (44.6, -42.2), (42.8, -40.6), (41.0, -42.2),
           (39.2, -40.6), (37.4, -42.2), (35.6, -40.6), (34.5, -39.0)], -3.4, 3.4)
latch = new_object("BarrelLatch", bm, M_STEEL, origin=P(40.0, -33.5), parent=gun)
bevel(latch, 0.35, 1, 50.0)

# антабка: прямоугольная проволочная скоба в пятке рукоятки
bm = bmesh.new()
path = fillet([(-45.0, -114.5, 3.0), (-27.0, -114.5, 3.0), (-27.0, -125.5, 3.0), (-45.0, -125.5, 3.0)])
rings = []
for i, (u, v) in enumerate(path):
    pu, pv = path[i - 1]
    nu, nv = path[(i + 1) % len(path)]
    tang = Vector((nu - pu, nv - pv)).normalized()
    norm = Vector((-tang.y, tang.x))
    rings.append([bm.verts.new(P(u + 1.4 * math.cos(math.tau * k / 10) * norm.x, v + 1.4 * math.cos(math.tau * k / 10) * norm.y,
                                 1.4 * math.sin(math.tau * k / 10))) for k in range(10)])
for i in range(len(rings)):
    r0, r1 = rings[i], rings[(i + 1) % len(rings)]
    for k in range(10):
        bm.faces.new((r0[k], r0[(k + 1) % 10], r1[(k + 1) % 10], r1[k]))
loop = new_object("LanyardLoop", bm, M_STEEL, origin=P(-36.0, -114.5), parent=gun)

# ---- щёчки рукоятки: пластик на стальной раме, ромб-накладка под винт
panel = fillet([(-34.0, -31.5, 6.0), (15.0, -31.5, 3.0), (19.0, -34.5, 2.0), (17.5, -43.0, 3.0), (12.0, -48.0, 5.0), (10.5, -72.0, 30.0),
                (-1.0, -104.0, 15.0), (-6.0, -112.5, 5.0), (-38.0, -112.5, 8.0), (-49.0, -99.0, 10.0), (-45.0, -45.0, 30.0), (-43.0, -36.0, 6.0)])
diamond = [(-16.0, -63.0), (-9.0, -76.0), (-16.0, -89.0), (-23.0, -76.0)]
for side_name, sign in (("L", 1.0), ("R", -1.0)):
    bm = bmesh.new()
    prism(bm, panel, sign * 5.0, sign * 13.0)
    grip = new_object("GripPanel_" + side_name, bm, M_GRIP, parent=gun)
    bevel(grip, 3.0, 4)
    bm = bmesh.new()
    prism(bm, diamond, sign * 12.0, sign * 13.9)
    esc = new_object("GripEscutcheon_" + side_name, bm, M_GRIP, parent=gun)
    bevel(esc, 0.7, 2)
bm = bmesh.new()
cyl_x(bm, -16.0, -76.0, 3.3, 13.0, 14.7)
cyl_x(bm, -16.0, -76.0, 3.3, -14.7, -13.0)
screws = new_object("GripScrews", bm, M_STEEL, parent=gun)
bevel(screws, 0.45, 2)

# ---- метки: срез ствола и место донца патрона (дочерние ствола — идут за ним при переломе)
for name, u in (("Muzzle", BARREL_L), ("Chamber", 0.0)):
    e = bpy.data.objects.new(name, None)
    scene.collection.objects.link(e)
    e.empty_display_size = 0.01
    e.parent = barrel
    e.location = P(u, 0.0) - barrel.location


# ---------------------------------------------------------------- патроны

def cartridge(name: str, mark, bumps: list, at: Vector):
    """26-мм сигнальный патрон одной деталью: донце с закраиной и капсюлем, картонная гильза, цветной пояс и
    крышка с бугорками (сколько их — отличие на ощупь). Начало — центр донца, ось — к дулу (−Y)."""
    bm_c = bmesh.new()
    prof = [(0.35, 3.4, 0), (0.0, 3.4, 0), (0.0, 13.4, 0), (0.3, 14.2, 0), (1.3, 14.2, 0), (1.6, 13.9, 0), (1.6, 13.1, 0), (6.0, 13.1, 0),
            (6.5, 12.8, 0), (7.0, 13.1, 0), (10.0, 13.1, 0), (10.5, 12.8, 0), (11.0, 13.1, 0), (14.0, 13.1, 1), (50.0, 13.1, 2),
            (58.0, 13.1, 1), (74.6, 13.1, 1), (76.0, 12.5, 1), (76.0, 11.7, 1), (74.6, 11.7, 2), (75.3, 11.0, 2)]
    lathe(bm_c, [(u, r) for u, r, _ in prof], closed=False, seg=24, caps=(True, True), mats=[m for _, _, m in prof])
    for x in bumps:
        lathe(bm_c, [(75.2, 2.7), (76.0, 2.5), (76.6, 1.7), (76.85, 0.8)], closed=False, seg=12, axis_x=x, caps=(False, True), mats=[2, 2, 2, 2])
    ob = new_object(name, bm_c, [M_HEAD, M_PAPER, mark])
    ob.data.transform(Matrix.Translation(-P(0.0, 0.0)))
    ob.location = at
    return ob


flare_red = cartridge("Flare_Red_Claude", M_RED, [0.0], Vector((0.10, 0.02, -0.03)))
flare_green = cartridge("Flare_Green_Claude", M_GREEN, [-4.6, 4.6], Vector((0.15, 0.02, -0.03)))

SRC.mkdir(parents=True, exist_ok=True)
txt = bpy.data.texts.new("Как устроено")
txt.from_string(__doc__ + "\nПерелом ствола: объект Barrel, поворот вокруг своей X (ось перелома — его начало), +50° — открыт.\n"
                "Спуск: Trigger, вокруг своей X. Защёлка: BarrelLatch, вокруг своей X. Антабка: LanyardLoop, вокруг своей Y.\n")
bpy.ops.wm.save_as_mainfile(filepath=str(SRC / "FlareGun_SP81_Claude_v01.blend"))

# ---------------------------------------------------------------- игровая копия: модификаторы, развёртка

meshes = [o for o in scene.objects if o.type == "MESH"]
for ob in meshes:
    bpy.context.view_layer.objects.active = ob
    for mod in list(ob.modifiers):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    ob.data.set_sharp_from_angle(angle=math.radians(40))
# ромб-накладка — часть щёчки
for side_name in ("L", "R"):
    bpy.ops.object.select_all(action="DESELECT")
    a, b = bpy.data.objects["GripPanel_" + side_name], bpy.data.objects["GripEscutcheon_" + side_name]
    a.select_set(True)
    b.select_set(True)
    bpy.context.view_layer.objects.active = a
    bpy.ops.object.join()
meshes = [o for o in scene.objects if o.type == "MESH"]
# развёртка: все детали одного материала — в одном поле 0–1 (одна карта на материал в UCUPaint)
by_material: dict = {}
for ob in meshes:
    key = ob.name if ob.name.startswith("Flare_") else ob.data.materials[0].name
    by_material.setdefault(key, []).append(ob)
for group in by_material.values():
    bpy.ops.object.select_all(action="DESELECT")
    for ob in group:
        ob.select_set(True)
        if not ob.data.uv_layers:
            ob.data.uv_layers.new(name="UVMap")
    bpy.context.view_layer.objects.active = group[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004, area_weight=0.0, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(margin=0.006, rotate=True)
    bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.select_all(action="DESELECT")

audit: dict = {"units": "m", "axes": "muzzle -Y, up +Z, +X shooter's left; origin = grip centre", "parts": {}}
lo = Vector((9, 9, 9))
hi = Vector((-9, -9, -9))
bpy.context.view_layer.update()
for ob in meshes:
    me = ob.data
    me.calc_loop_triangles()
    uvs = [d.uv for d in me.uv_layers[0].data]
    audit["parts"][ob.name] = {"tris": len(me.loop_triangles), "materials": [m.name for m in me.materials],
                               "uv_in_0_1": all(-1e-4 <= c <= 1.0001 for uv in uvs for c in uv)}
    if not ob.name.startswith("Flare_"):
        for v in me.vertices:
            w = ob.matrix_world @ v.co
            lo = Vector((min(lo.x, w.x), min(lo.y, w.y), min(lo.z, w.z)))
            hi = Vector((max(hi.x, w.x), max(hi.y, w.y), max(hi.z, w.z)))
audit["gun_size_mm"] = {"width_x": round((hi.x - lo.x) * 1000, 1), "length_y": round((hi.y - lo.y) * 1000, 1), "height_z_with_loop": round((hi.z - lo.z) * 1000, 1)}
audit["gun_tris"] = sum(p["tris"] for n, p in audit["parts"].items() if not n.startswith("Flare_"))
audit["cartridge_tris"] = audit["parts"]["Flare_Red_Claude"]["tris"]
audit["cartridge_mm"] = {"length": 76.85, "case": 26.2, "rim": 28.4}
audit["bore_mm"] = BORE_R * 2
audit["barrel_mm"] = {"outer": BARREL_R * 2, "length": BARREL_L}
(SRC / "asset-audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8")
print("FLARE audit", audit["gun_size_mm"], "tris", audit["gun_tris"], "cartridge", audit["cartridge_tris"],
      "uv", all(p["uv_in_0_1"] for p in audit["parts"].values()), flush=True)
bpy.ops.wm.save_as_mainfile(filepath=str(SRC / "FlareGun_SP81_Claude_v01_game.blend"))

# ---------------------------------------------------------------- GLB

OUT.mkdir(parents=True, exist_ok=True)


def export(root, name: str) -> None:
    keep = root.location.copy()
    root.location = Vector((0, 0, 0))
    bpy.ops.object.select_all(action="DESELECT")
    stack = [root]
    while stack:
        ob = stack.pop()
        ob.select_set(True)
        stack.extend(ob.children)
    bpy.ops.export_scene.gltf(filepath=str(OUT / name), export_format="GLB", use_selection=True, export_yup=True,
                              export_apply=True, export_animations=False, export_tangents=True)
    root.location = keep


export(gun, "flare_gun_claude.glb")
export(flare_red, "flare_red_claude.glb")
export(flare_green, "flare_green_claude.glb")

# ---------------------------------------------------------------- превью

scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x, scene.render.resolution_y = 1600, 1000
scene.render.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("Просмотр")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.62, 0.64, 0.67, 1.0)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.7
scene.world = world
for name, rot, energy in (("Ключ", (50, 0, 35), 2.4), ("Заполнение", (60, 0, -140), 1.0), ("Контур", (-30, 0, 120), 0.8)):
    light = bpy.data.objects.new(name, bpy.data.lights.new(name, "SUN"))
    light.data.energy = energy
    light.rotation_euler = [math.radians(a) for a in rot]
    scene.collection.objects.link(light)
cam = bpy.data.objects.new("Камера", bpy.data.cameras.new("Камера"))
cam.data.lens = 85
cam.data.clip_start = 0.01
scene.collection.objects.link(cam)
scene.camera = cam
VIEW = SRC / "Просмотр"
VIEW.mkdir(exist_ok=True)
for old in VIEW.glob("*.png"):
    old.unlink()


def shot(name: str, offset: Vector, target: Vector) -> None:
    cam.location = target + offset
    z = offset.normalized()
    x = Vector((0, 0, 1)).cross(z).normalized()
    m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
    m.translation = cam.location
    cam.matrix_world = m
    scene.render.filepath = str(VIEW / (name + ".png"))
    bpy.ops.render.render(write_still=True)


centre = Vector((0.0, -0.058, 0.015))
flare_red.hide_render = True
flare_green.hide_render = True
shot("01_sleva", Vector((0.72, 0.0, 0.0)), centre)
shot("02_sprava", Vector((-0.72, 0.0, 0.0)), centre)
shot("03_tri_chetverti", Vector((0.46, -0.5, 0.22)), centre)
shot("04_szadi_sverhu", Vector((0.3, 0.55, 0.36)), centre)
shot("05_snizu_speredi", Vector((-0.36, -0.5, -0.3)), centre)
# переломлен, патроны рядом
barrel.rotation_euler = (math.radians(50), 0, 0)
for ob, x in ((flare_red, 0.07), (flare_green, 0.12)):
    ob.hide_render = False
    ob.location = Vector((x, -0.03, -0.055))
    ob.rotation_euler = (math.radians(-90), 0, 0)
shot("06_perelomlen_s_patronami", Vector((0.62, -0.5, 0.3)), Vector((0.03, -0.07, 0.0)))
shot("07_perelomlen_szadi", Vector((0.18, 0.5, 0.3)), Vector((0.0, -0.05, 0.03)))
shot("08_patrony", Vector((0.22, -0.2, 0.2)), Vector((0.095, -0.03, -0.02)))
shot("09_patrony_dontsa", Vector((0.14, -0.14, -0.26)), Vector((0.095, -0.03, -0.05)))
print("FLARE done", flush=True)
