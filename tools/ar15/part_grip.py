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
TOP_CX = -147.0                 # ось рукояти на верхней площадке (перёд — у заднего уха скобы)
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
# канавки под пальцы на передней кромке — ниже скобы (она примыкает к рукояти до t ≈ 0.3): канавки 0.40 / 0.64 / 0.87
# (z ≈ −89 / −112 / −135 — средний, безымянный, мизинец), гребни 0.52 и 0.75; выше t 0.30 кромка гладкая под скобу
FINGER_AMP = 1.9
FINGER_PERIOD = 0.233
FINGER_RIDGE = 0.52
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
    env = _smooth(0.30, 0.36, t) * (1.0 - _smooth(0.90, 0.95, t))
    f += FINGER_AMP * env * math.cos(2 * math.pi * (t - FINGER_RIDGE) / FINGER_PERIOD)
    return f, b, w


def front_xz(t, gap=0.0):
    """Передняя кромка рукояти по средней плоскости (мм), сдвинутая вперёд на gap — по ней идёт задняя грань скобы."""
    f, _b, _w = section_at(t)
    p = axis_pt(t) + FWD * (f + gap)
    return p.x, p.z


def ring(t, f, b, w, n=96):
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


PANEL_T = (0.18, 0.83)           # площадка по длине рукояти (доли)
PANEL_U = (-0.50, 0.44)          # и поперёк (доли полуоси сечения от середины: назад … вперёд)
PANEL_DEPTH = 0.6
STIP_PITCH = 1.7
SCREW_OFF = -11.1                # винт смещён назад от оси рукояти, чтобы попасть в отверстие ресивера
U_TOP = LEN + SCREW_OFF * math.tan(math.radians(ANGLE))   # где ось винта пересекает площадку (от низа рукояти по оси)
SCREW_HEAD_D = 18.0              # головка винта на 18 мм ниже площадки, стержень входит в ресивер на 7 мм


def _panel_pt(t, uf, s, dy):
    f, b, w = section_at(t)
    c, hx = (f + b) / 2, (f - b) / 2
    xl = c + uf * hx
    p = axis_pt(t) + FWD * xl
    return Vector((p.x, s * (surf_y(t, xl) + dy), p.z))


def panel_cutter(s, G, nt=44, nu=18):
    """Срез площадки: тело между поверхностью рукояти минус PANEL_DEPTH и +3 мм наружу, по сетке (t, u)."""
    me = bpy.data.meshes.new("cut_grip_panel")
    bm = bmesh.new()
    ts = [PANEL_T[0] + (PANEL_T[1] - PANEL_T[0]) * i / (nt - 1) for i in range(nt)]
    us = [PANEL_U[0] + (PANEL_U[1] - PANEL_U[0]) * j / (nu - 1) for j in range(nu)]
    inner = [[bm.verts.new(v(*_panel_pt(t, u, s, -PANEL_DEPTH))) for u in us] for t in ts]
    outer = [[bm.verts.new(v(*_panel_pt(t, u, s, 3.0))) for u in us] for t in ts]
    for i in range(nt - 1):
        for j in range(nu - 1):
            bm.faces.new((inner[i][j], inner[i][j + 1], inner[i + 1][j + 1], inner[i + 1][j]))
            bm.faces.new((outer[i][j], outer[i + 1][j], outer[i + 1][j + 1], outer[i][j + 1]))
    for i in range(nt - 1):
        bm.faces.new((inner[i][0], inner[i + 1][0], outer[i + 1][0], outer[i][0]))
        bm.faces.new((inner[i][-1], outer[i][-1], outer[i + 1][-1], inner[i + 1][-1]))
    for j in range(nu - 1):
        bm.faces.new((inner[0][j], outer[0][j], outer[0][j + 1], inner[0][j + 1]))
        bm.faces.new((inner[-1][j], inner[-1][j + 1], outer[-1][j + 1], outer[-1][j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new("cut_grip_panel", me)
    G.objects.link(o)
    return o


def stipple(G):
    """Бугорки в шахматном порядке по дну площадок; каждый — замкнутое тело, основание на 0.25 мм в дне."""
    me = bpy.data.meshes.new("grip_texture")
    tb = bmesh.new()
    margin = 0.9
    for s in (-1, 1):
        tm = PANEL_T[0] * LEN + margin + 0.6
        row = 0
        while tm <= PANEL_T[1] * LEN - margin - 0.6:
            t = tm / LEN
            f, b, w = section_at(t)
            c, hx = (f + b) / 2, (f - b) / 2
            x_lo = c + PANEL_U[0] * hx + margin + 0.6
            x_hi = c + PANEL_U[1] * hx - margin - 0.6
            xl = x_lo + (STIP_PITCH / 2 if row % 2 else 0.0)
            while xl <= x_hi:
                ys = surf_y(t, xl) - PANEL_DEPTH
                base = axis_pt(t) + FWD * xl
                quads = []
                for half, dy in ((0.55, -0.25), (0.28, 0.38)):
                    q = []
                    for du, dv in ((-half, -half), (half, -half), (half, half), (-half, half)):
                        p = base + FWD * du + DOWN * dv
                        q.append(tb.verts.new(v(p.x, s * (ys + dy), p.z)))
                    quads.append(q)
                lo, hi = quads
                tb.faces.new(lo)
                tb.faces.new(list(reversed(hi)))
                for k in range(4):
                    k2 = (k + 1) % 4
                    tb.faces.new((lo[k], hi[k], hi[k2], lo[k2]))
                xl += STIP_PITCH
            tm += STIP_PITCH * 0.866
            row += 1
    bmesh.ops.recalc_face_normals(tb, faces=tb.faces)
    tb.to_mesh(me); tb.free()
    tex = bpy.data.objects.new("grip_texture", me)
    G.objects.link(tex)
    tex.data.materials.append(material("Polymer"))
    for p in tex.data.polygons:
        p.use_smooth = False
    return tex


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
    dz = GRIP_TOP_Z + 45.9
    bt = prism_xz("grip_beavertail", fillet([(-168.0, GRIP_TOP_Z), (-186.6, GRIP_TOP_Z), (-190.5, -44.6 + dz), (-196.4, -42.2 + dz),
                                             (-198.6, -44.2 + dz), (-196.8, -48.6 + dz), (-189.0, -58.0 + dz), (-170.0, -62.0 + dz)],
                                            [0, 1.5, 2.5, 2.5, 2.0, 4.0, 4.0, 0], 4), -10.5, 10.5, G, "Polymer")
    finish(bt, w=1.6, seg=3, angle=30)
    boolean(grip, bt, "UNION")
    # отверстие под винт снизу: ось винта параллельна оси рукояти и выходит на площадку под отверстием ресивера (x −158.6)
    bottom = axis_pt(1.0) + FWD * SCREW_OFF
    # канал под ключ снизу до головки винта и проход стержня через верх рукояти в ресивер
    hole = lathe("cut_grip_screw", [(-1.0, 0.0), (-1.0, 5.2), (U_TOP - SCREW_HEAD_D + 4.05, 5.2), (U_TOP - SCREW_HEAD_D + 4.05, 3.3),
                                    (U_TOP + 1.5, 3.3), (U_TOP + 1.5, 0.0)], G, None, seg=40, cy=0.0, cz=0.0)
    hole.rotation_euler = (0, math.radians(-90 + ANGLE), 0)
    hole.location = v(bottom.x, 0, bottom.z)
    apply_transform(hole)
    boolean(grip, hole)
    finish(grip, w=0.9, seg=3, angle=40)
    # утопленные площадки текстуры по бокам (срез по поверхности рукояти на PANEL_DEPTH)
    for s_ in (-1, 1):
        boolean(grip, panel_cutter(s_, G))
    finish(grip, w=0.3, seg=2, angle=40)
    for p in grip.data.polygons:
        p.use_smooth = True
    # бугорки на дне площадок — замкнутые усечённые пирамидки (основание утоплено в дно)
    tex = stipple(G)
    grip = join([grip, tex], "Pistol_grip")
    auto_sharp(grip, 40)
    grip["_fin"] = 1
    o["grip"] = grip
    # винт рукояти: головка с шестигранником в глубине отверстия, хвост вверх по оси
    u0 = U_TOP - SCREW_HEAD_D
    # стержень по внутреннему диаметру резьбы (r 2.4) — входит в резьбовое отверстие ресивера (r 2.6, 20 граней) без пересечения
    sc = lathe("Grip_screw", [(u0, 0.0), (u0, 3.6), (u0 + 0.4, 4.0), (u0 + 3.6, 4.0), (u0 + 4.0, 3.4), (u0 + 4.0, 2.4),
                              (U_TOP + 6.4, 2.4), (U_TOP + 7.0, 1.9), (U_TOP + 7.0, 0.0)], G, "Steel_black", seg=40, cy=0.0, cz=0.0)
    hexa = prism_yz("cut_screw_hex", [(1.9 * math.cos(math.radians(60 * k + 30)), 1.9 * math.sin(math.radians(60 * k + 30))) for k in range(6)],
                    u0 - 1.0, u0 + 2.4, G)
    boolean(sc, hexa)
    for k in range(int(10.0 / 1.06)):
        uu = U_TOP - 3.0 + k * 1.06
        boolean(sc, lathe("cut_scr_thread", [(uu - 0.3, 2.5), (uu, 2.05), (uu + 0.3, 2.5)], G, None, seg=40))
    sc.rotation_euler = (0, math.radians(-90 + ANGLE), 0)
    sc.location = v(bottom.x, 0, bottom.z)
    apply_transform(sc)
    finish(sc, w=0.15, seg=2, angle=40)
    o["screw"] = sc
    return o
