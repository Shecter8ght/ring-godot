# AR-15: пистолетная рукоять в манере листинга Fab — почти вертикальная (18° от вертикали), упор ладони сзади-сверху,
# спереди канавки под средний, безымянный палец и мизинец с гребнями между ними (владелец, 2026-10-29: «рукоятка должна
# быть с выступами под пальцы»), расширение внизу, мелкая «точечная» текстура по бокам; винт рукояти снизу по её оси.
# Верх — плоская площадка на GRIP_TOP_Z (под нижним ресивером).
import math
import bmesh
import bpy
from mathutils import Vector
from lib import (MM, GRIP_TOP_Z, GRIP_TOP_X, v, fillet, prism_xz, prism_xy, prism_yz, box, cyl, lathe, boolean, finish, auto_sharp,
                 apply_transform, join, material)

ANGLE = 18.0
LEN = 104.0                     # длина по оси от верхней площадки
TOP_CX = -156.0                 # ось рукояти на верхней площадке
P_EXP = 2.8                     # «квадратность» сечения
# t (доля длины), вперёд f, назад b (вдоль поперечной оси), полуширина w
SECTIONS = [
    (-0.12, 24.0, -24.0, 14.6),
    (0.00, 24.0, -24.0, 14.6),
    (0.12, 23.6, -23.2, 14.6),
    (0.24, 23.6, -22.2, 14.8),
    (0.34, 23.2, -21.4, 15.0),
    (0.50, 22.6, -20.8, 15.1),
    (0.66, 22.8, -20.8, 15.2),
    (0.80, 23.6, -21.4, 15.5),
    (0.90, 25.0, -22.6, 16.2),
    (0.965, 25.6, -23.4, 16.6),
    (0.99, 25.0, -22.9, 16.2),
    (1.00, 23.8, -21.8, 15.3),
]
# канавки под пальцы на передней кромке: гребни в t ≈ 0.37 и 0.66, канавки 0.22 / 0.51 / 0.80 (шаг ≈ 30 мм — палец)
FINGER_AMP = 1.9
FINGER_PERIOD = 0.29
FINGER_RIDGE = 0.37
STATIONS = [-0.12, -0.06] + [round(0.0 + 0.0125 * k, 4) for k in range(81)]
SA, CA = math.sin(math.radians(ANGLE)), math.cos(math.radians(ANGLE))
DOWN = Vector((-SA, 0.0, -CA))          # ось рукояти вниз
FWD = Vector((CA, 0.0, -SA))            # поперечная ось «вперёд»
TOP = Vector((TOP_CX, 0.0, GRIP_TOP_Z))


def axis_pt(t):
    return TOP + DOWN * (t * LEN)


def _smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def section_at(t):
    base = SECTIONS[-1][1:]
    for (t0, f0, b0, w0), (t1, f1, b1, w1) in zip(SECTIONS, SECTIONS[1:]):
        if t0 <= t <= t1:
            k = (t - t0) / (t1 - t0)
            base = (f0 + (f1 - f0) * k, b0 + (b1 - b0) * k, w0 + (w1 - w0) * k)
            break
    f, b, w = base
    env = _smooth(0.08, 0.17, t) * (1.0 - _smooth(0.84, 0.93, t))
    f += FINGER_AMP * env * math.cos(2 * math.pi * (t - FINGER_RIDGE) / FINGER_PERIOD)
    return f, b, w


def ring(t, f, b, w, n=56):
    c, hx = (f + b) / 2, (f - b) / 2
    a0 = axis_pt(t)
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        ca, sa = math.cos(a), math.sin(a)
        xl = c + hx * math.copysign(abs(ca) ** (2 / P_EXP), ca)
        y = w * math.copysign(abs(sa) ** (2 / P_EXP), sa)
        p = a0 + FWD * xl
        pts.append(Vector((p.x, y, p.z)))
    return pts


def surf_y(t, xl):
    f, b, w = section_at(t)
    c, hx = (f + b) / 2, (f - b) / 2
    u = min(1.0, abs((xl - c) / hx))
    return w * (1.0 - u ** P_EXP) ** (1.0 / P_EXP)


def build(ctx):
    G = ctx["coll"]["Grip"]
    o = {}
    me = bpy.data.meshes.new("Pistol_grip")
    bm = bmesh.new()
    rings = []
    for t in STATIONS:
        f, b, w = section_at(t)
        rings.append([bm.verts.new(v(p.x, p.y, p.z)) for p in ring(t, f, b, w)])
    n = len(rings[0])
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    grip = bpy.data.objects.new("Pistol_grip", me)
    G.objects.link(grip)
    grip.data.materials.append(material("Polymer"))
    auto_sharp(grip, 50)
    # плоская площадка сверху — срез по низу ресивера
    boolean(grip, box("grip_clip", -400, 0, -60, 60, -300, GRIP_TOP_Z, G), "INTERSECT")
    # упор ладони сзади-сверху: заходит за задний торец нижнего ресивера, ниже пластины приклада
    bt = prism_xz("grip_beavertail", fillet([(-172.0, GRIP_TOP_Z), (-186.6, GRIP_TOP_Z), (-190.5, -44.6), (-196.4, -42.2),
                                             (-198.6, -44.2), (-196.8, -48.6), (-189.0, -58.0), (-176.0, -60.0)],
                                            [0, 1.5, 2.5, 2.5, 2.0, 4.0, 4.0, 0], 4), -10.5, 10.5, G, "Polymer")
    finish(bt, w=1.6, seg=3, angle=30)
    boolean(grip, bt, "UNION")
    # отверстие под винт снизу (по оси, чуть назад)
    bottom = axis_pt(1.0) + FWD * (-2.0)
    hole = lathe("cut_grip_screw", [(-1.0, 0.0), (-1.0, 5.2), (20.0, 5.2), (20.0, 0.0)], G, None, seg=32, cy=0.0, cz=0.0)
    hole.rotation_euler = (0, math.radians(-90 + ANGLE), 0)
    hole.location = v(bottom.x, 0, bottom.z)
    apply_transform(hole)
    boolean(grip, hole)
    # торцы (низ и площадка) — плоское затенение, иначе гладкие нормали на больших треугольниках дают «звёзды»
    for p in grip.data.polygons:
        n = p.normal
        if n.dot(DOWN) > 0.96 or n.z > 0.96:
            p.use_smooth = False
    finish(grip, w=0.9, seg=3, angle=40)
    o["grip"] = grip
    # точечная текстура по бокам: пирамидки на поверхности
    tme = bpy.data.meshes.new("grip_texture")
    tb = bmesh.new()
    pitch = 1.6
    half = 0.5
    for s in (-1, 1):
        tm = 0.16 * LEN
        while tm <= 0.84 * LEN:
            t = tm / LEN
            f, b, w = section_at(t)
            c, hx = (f + b) / 2, (f - b) / 2
            row = int(round(tm / pitch))
            xl = c - 0.52 * hx + (pitch / 2 if row % 2 else 0.0)
            while xl <= c + 0.52 * hx:
                ys = surf_y(t, xl)
                base = axis_pt(t) + FWD * xl
                corners = []
                for du, dv in ((-half, -half), (half, -half), (half, half), (-half, half)):
                    p = base + FWD * du + DOWN * dv
                    corners.append(tb.verts.new(v(p.x, s * (ys - 0.3), p.z)))
                apex = tb.verts.new(v(base.x, s * (ys + 0.42), base.z))
                for i in range(4):
                    a, bb = corners[i], corners[(i + 1) % 4]
                    tb.faces.new((a, bb, apex) if s > 0 else (bb, a, apex))
                xl += pitch
            tm += pitch * 0.866
    bmesh.ops.recalc_face_normals(tb, faces=tb.faces)
    tb.to_mesh(tme); tb.free()
    tex = bpy.data.objects.new("grip_texture", tme)
    G.objects.link(tex)
    tex.data.materials.append(material("Polymer"))
    for p in tex.data.polygons:
        p.use_smooth = False
    grip = join([grip, tex], "Pistol_grip")
    grip["_fin"] = 1
    o["grip"] = grip
    # винт рукояти: головка с шестигранником в глубине отверстия, хвост вверх по оси
    sc = lathe("Grip_screw", [(19.0, 0.0), (19.0, 3.6), (19.4, 4.0), (23.4, 4.0), (23.6, 3.2), (23.6, 3.1), (34.0, 3.1),
                              (34.4, 2.7), (34.4, 0.0)], G, "Steel_black", seg=32, cy=0.0, cz=0.0)
    hexa = prism_yz("cut_screw_hex", [(1.9 * math.cos(math.radians(60 * k + 30)), 1.9 * math.sin(math.radians(60 * k + 30))) for k in range(6)],
                    18.0, 21.4, G)
    boolean(sc, hexa)
    sc.rotation_euler = (0, math.radians(-90 + ANGLE), 0)
    sc.location = v(bottom.x, 0, bottom.z)
    apply_transform(sc)
    auto_sharp(sc, 35)
    o["screw"] = sc
    return o
