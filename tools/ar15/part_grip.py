# AR-15: пистолетная рукоять, эргономичная (владелец, 2026-10-29: «рукоятка слишком примитивная и без нужных изгибов» —
# по образцам: рукоять STM-416 на снимке владельца и рукоять AR15 Lokeig на Sketchfab). Сверху — упор ладони
# («бобровый хвост») с вогнутым «седлом» под ним, куда ложится перепонка между большим и указательным пальцами;
# сзади — выпуклость под ладонь, внизу — расширение пятки. Верх спинки кончается заподлицо с задним срезом нижнего
# ресивера (владелец: «аккуратно заканчивается там, где идёт задний срез», не вылезает назад). Спереди сверху — выступ
# вперёд до задней стойки скобы, шов с ней вертикальный (владелец, по образцу); ниже выступа — три выемки под средний,
# безымянный палец и мизинец с поперечными рёбрышками внутри; по бокам — утопленные площадки с точечной текстурой.
# Тело — сечения по горизонтали (z) от площадки под ресивером вниз, дно — срез перпендикулярно оси рукояти (18°).
# Винт рукояти — снизу по её оси, в отверстие ресивера (x −158.6).
import math
import bmesh
import bpy
from mathutils import Vector
from lib import (MM, GRIP_TOP_Z, v, prism_xz, prism_yz, lathe, boolean, finish, auto_sharp, apply_transform, join, material)

ANGLE = 18.0
LEN = 104.0                     # длина по оси от верхней площадки до дна
TOP_CX = -147.0                 # ось рукояти на верхней площадке
SA, CA = math.sin(math.radians(ANGLE)), math.cos(math.radians(ANGLE))
DOWN = Vector((-SA, 0.0, -CA))          # ось рукояти вниз
FWD = Vector((CA, 0.0, -SA))            # поперечная ось «вперёд»
TOP = Vector((TOP_CX, 0.0, GRIP_TOP_Z))

SLOPE = math.tan(math.radians(ANGLE))
FRONT_TOP_X = -118.6            # прежняя линия переда (18°) — от неё считаются выемки под пальцами
GUARD_POST_X = -118.6           # задняя грань стойки скобы (нижний ресивер: GUARD_X[0] − 5)
LUG_SEAM = 0.1                  # вертикальный шов между выступом рукояти и стойкой скобы (подгонка без пустот)
LUG_X = GUARD_POST_X + 2.6      # перёд выступа выведен за стойку и срезан плоскостью шва — плоский по всей ширине
LUG_Z = -77.9                   # низ выступа = низ перекладины скобы; ниже перёд уходит в выемку под средний палец
# выемки под пальцы ниже перекладины скобы (её низ z −77.9): (верх, низ, глубина), гребни между ними — z −100.5 и −121.5
GROOVES = [(-78.0, -100.5, 5.8), (-100.5, -121.5, 5.2), (-121.5, -140.0, 4.2)]
GROOVE_KERNEL = [(-1.8, 0.06), (-1.2, 0.12), (-0.6, 0.2), (0.0, 0.24), (0.6, 0.2), (1.2, 0.12), (1.8, 0.06)]   # скругление гребней
Z_BOTTOM = -153.0               # нижнее сечение (ниже наклонного дна — срезается)
Z_RING_TOP = -37.0              # верхнее сечение: выше площадки, срезается по ней и по подъёму «хвоста»
DZ = 0.5                        # шаг сечений
N_RING = 128
P_FRONT, P_BACK = 2.7, 2.4      # «квадратность» передней и задней половин сечения
P_LUG = 6.0                     # у выступа перёд площе: после среза плоскость шва идёт на всю ширину низа ресивера


def _smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def _pchip(points):
    """Монотонная кубическая интерполяция (Фрич — Карлсон) по точкам (z, значение)."""
    pts = sorted(points)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    n = len(xs)
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [0.0] * n
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])

    def f(x):
        if x <= xs[0]:
            return ys[0] + m[0] * (x - xs[0])
        if x >= xs[-1]:
            return ys[-1] + m[-1] * (x - xs[-1])
        for i in range(n - 1):
            if xs[i] <= x <= xs[i + 1]:
                t = (x - xs[i]) / h[i]
                t2, t3 = t * t, t * t * t
                return ((2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h[i] * m[i] + (-2 * t3 + 3 * t2) * ys[i + 1]
                        + (t3 - t2) * h[i] * m[i + 1])
    return f


# спинка (по средней плоскости): «бобровый хвост» сверху → седло под ним (z ≈ −65) → выпуклость под ладонь (≈ −100) → пятка
BACK_X = _pchip([(-42.0, -186.0), (-44.0, -186.4), (-46.5, -186.5), (-49.0, -185.7), (-51.5, -183.8), (-54.0, -181.2),
                 (-57.0, -178.3), (-60.5, -175.9), (-64.5, -174.6), (-69.0, -174.6), (-74.0, -176.4), (-82.0, -179.4),
                 (-92.0, -184.6), (-100.0, -187.8), (-110.0, -190.3), (-120.0, -192.6), (-130.0, -196.4), (-137.0, -200.2),
                 (-142.0, -201.0), (-160.0, -201.0)])
# полуширина: у площадки 14.6 (рукоять 29.2), под ладонью 15.6, внизу расширение 16.4
HALF_W = _pchip([(-42.0, 14.6), (-60.0, 14.7), (-80.0, 15.0), (-100.0, 15.6), (-118.0, 15.4), (-134.0, 15.6), (-142.0, 16.4),
                 (-160.0, 16.4)])


def axis_pt(t):
    return TOP + DOWN * (t * LEN)


def _groove_raw(z):
    g = 0.0
    for z0, z1, d in GROOVES:
        if z1 <= z <= z0:
            g += d * math.sin(math.pi * (z0 - z) / (z0 - z1)) ** 0.75
    return g


def groove_depth(z):
    return sum(w * _groove_raw(z + dz) for dz, w in GROOVE_KERNEL)


def _lug_w(z):
    """Доля выступа: 1 от площадки до низа скобы, ниже за 9 мм плавно уходит в линию выемок."""
    return 1.0 - _smooth(LUG_Z, LUG_Z - 9.0, z)


def front_x(z):
    """Перёд рукояти по средней плоскости: выступ вертикально у стойки скобы (до её низа), ниже — выемки под пальцы
    по прежней линии 18°, внизу — губа вперёд."""
    base = FRONT_TOP_X + SLOPE * (z - GRIP_TOP_Z)
    line = base - groove_depth(z) + 3.6 * _smooth(-139.0, -149.0, z)
    return line + (LUG_X - line) * _lug_w(z)


def p_front(z):
    return P_FRONT + (P_LUG - P_FRONT) * _lug_w(z)


def back_x(z):
    return BACK_X(z)


def front_xz(t, gap=0.0):
    """Передняя кромка рукояти по средней плоскости (мм), сдвинутая вперёд на gap — по ней идёт задняя грань скобы.
    t — параметр по высоте: z = −49.4 − 98.9·t (убывает с t; −0.08 → над площадкой, 0.3775 → ниже перекладины скобы)."""
    z = -49.4 - 98.9 * t
    x = front_x(z)
    return x + FWD.x * gap, z + FWD.z * gap


def _taper(x, z):
    """Верх спинки у заднего среза сужается до ширины нижнего ресивера (±12.2)."""
    return 1.0 - 0.16 * _smooth(-176.0, -186.0, x) * _smooth(-56.0, -46.0, z)


def section(z):
    xb, xf = back_x(z), front_x(z)
    return xb, xf, HALF_W(z)


def ring(z, n=N_RING):
    xb, xf, w = section(z)
    c, hx = (xf + xb) / 2, (xf - xb) / 2
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        ca, sa = math.cos(a), math.sin(a)
        p = p_front(z) if ca >= 0 else P_BACK
        x = c + hx * math.copysign(abs(ca) ** (2 / p), ca)
        y = w * math.copysign(abs(sa) ** (2 / p), sa) * _taper(x, z)
        pts.append((x, y, z))
    return pts


def surf_y(z, x):
    """Полуширина поверхности рукояти в точке x сечения z."""
    xb, xf, w = section(z)
    c, hx = (xf + xb) / 2, (xf - xb) / 2
    u = min(1.0, abs((x - c) / hx))
    p = p_front(z) if x >= c else P_BACK
    return w * (1.0 - u ** p) ** (1.0 / p) * _taper(x, z)


def bottom_plane_z(x):
    """Дно рукояти — плоскость, перпендикулярная её оси, через конец оси."""
    a = axis_pt(1.0)
    return a.z - (SA / CA) * (x - a.x)


# утопленные площадки с текстурой по бокам: по высоте и поперёк (доли полудлины сечения от середины: −1 спинка … +1 перёд)
PANEL_Z = (-82.5, -139.5)
PANEL_U = (-0.74, 0.60)
PANEL_DEPTH = 0.7
STIP_PITCH = 1.7
# рёбрышки в выемках под пальцы: шаг, высота над поверхностью, ширина основания, доля ширины переда
RIB_PITCH = 2.6
RIB_H = 0.45
RIB_HALF = 0.5
RIB_SPAN = 0.55
SCREW_OFF = -11.1                # винт смещён назад от оси рукояти, чтобы попасть в отверстие ресивера
U_TOP = LEN + SCREW_OFF * math.tan(math.radians(ANGLE))   # где ось винта пересекает площадку (от низа рукояти по оси)
SCREW_HEAD_D = 18.0              # головка винта на 18 мм ниже площадки, стержень входит в ресивер на 7 мм


def _panel_range(z):
    """Пределы площадки поперёк на высоте z: прямоугольник со скруглёнными углами в координатах (z, u)."""
    zc, zh = (PANEL_Z[0] + PANEL_Z[1]) / 2, (PANEL_Z[0] - PANEL_Z[1]) / 2
    s = min(1.0, abs(z - zc) / zh)
    k = max(0.0, (s - 0.72) / 0.28)
    f = max(0.18, math.sqrt(max(0.0, 1.0 - k * k)))
    uc, hu = (PANEL_U[0] + PANEL_U[1]) / 2, (PANEL_U[1] - PANEL_U[0]) / 2
    return uc - hu * f, uc + hu * f


def _panel_pt(z, u, s, dy):
    xb, xf, _w = section(z)
    c, hx = (xf + xb) / 2, (xf - xb) / 2
    x = c + u * hx
    return x, s * (surf_y(z, x) + dy), z


def panel_cutter(s, G, nz=60, nu=22):
    """Срез площадки: тело между поверхностью рукояти минус PANEL_DEPTH и +3 мм наружу, по сетке (z, u)."""
    me = bpy.data.meshes.new("cut_grip_panel")
    bm = bmesh.new()
    zs = [PANEL_Z[0] + (PANEL_Z[1] - PANEL_Z[0]) * i / (nz - 1) for i in range(nz)]
    inner, outer = [], []
    for z in zs:
        u0, u1 = _panel_range(z)
        us = [u0 + (u1 - u0) * j / (nu - 1) for j in range(nu)]
        inner.append([bm.verts.new(v(*_panel_pt(z, u, s, -PANEL_DEPTH))) for u in us])
        outer.append([bm.verts.new(v(*_panel_pt(z, u, s, 3.0))) for u in us])
    for i in range(nz - 1):
        for j in range(nu - 1):
            bm.faces.new((inner[i][j], inner[i][j + 1], inner[i + 1][j + 1], inner[i + 1][j]))
            bm.faces.new((outer[i][j], outer[i + 1][j], outer[i + 1][j + 1], outer[i][j + 1]))
    for i in range(nz - 1):
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


def _closed_bump(tb, quads):
    lo, hi = quads
    tb.faces.new(lo)
    tb.faces.new(list(reversed(hi)))
    for k in range(4):
        k2 = (k + 1) % 4
        tb.faces.new((lo[k], hi[k], hi[k2], lo[k2]))


def stipple(G):
    """Бугорки в шахматном порядке по дну площадок; каждый — замкнутое тело, основание на 0.25 мм в дне."""
    me = bpy.data.meshes.new("grip_texture")
    tb = bmesh.new()
    margin = 1.0
    for s in (-1, 1):
        z = PANEL_Z[0] - margin - 0.6
        row = 0
        while z >= PANEL_Z[1] + margin + 0.6:
            u0, u1 = _panel_range(z)
            xb, xf, _w = section(z)
            c, hx = (xf + xb) / 2, (xf - xb) / 2
            x_lo, x_hi = c + u0 * hx + margin + 0.6, c + u1 * hx - margin - 0.6
            x = x_lo + (STIP_PITCH / 2 if row % 2 else 0.0)
            while x <= x_hi:
                ys = surf_y(z, x) - PANEL_DEPTH
                base = Vector((x, 0.0, z))
                quads = []
                for half, dy in ((0.55, -0.25), (0.28, 0.38)):
                    q = []
                    for du, dv in ((-half, -half), (half, -half), (half, half), (-half, half)):
                        p = base + FWD * du + DOWN * dv
                        q.append(tb.verts.new(v(p.x, s * (ys + dy), p.z)))
                    quads.append(q)
                _closed_bump(tb, quads)
                x += STIP_PITCH
            z -= STIP_PITCH * 0.866
            row += 1
    bmesh.ops.recalc_face_normals(tb, faces=tb.faces)
    tb.to_mesh(me); tb.free()
    tex = bpy.data.objects.new("grip_texture", me)
    G.objects.link(tex)
    tex.data.materials.append(material("Polymer"))
    for p in tex.data.polygons:
        p.use_smooth = False
    return tex


def _front_arc(z, half_span):
    """Точки передней дуги сечения z (|y| ≤ half_span) и нормали к ней в плоскости XY (наружу)."""
    xb, xf, w = section(z)
    c, hx = (xf + xb) / 2, (xf - xb) / 2
    p = p_front(z)
    out = []
    n = max(8, int(2 * half_span / 0.45))
    for k in range(n + 1):
        y = -half_span + 2 * half_span * k / n
        r = min(0.999, abs(y) / w)
        x = c + hx * (1.0 - r ** p) ** (1.0 / p)
        # производная dx/dy по суперэллипсу
        if r > 1e-6:
            dxdy = -hx * (1.0 - r ** p) ** (1.0 / p - 1.0) * r ** (p - 1.0) / w * math.copysign(1.0, y)
        else:
            dxdy = 0.0
        nx, ny = 1.0, -dxdy
        ln = math.hypot(nx, ny)
        out.append((x, y, nx / ln, ny / ln, abs(y) / half_span))
    return out


def ribs(G):
    """Поперечные рёбрышки в выемках под пальцы: замкнутые бруски по передней дуге, основание утоплено на 0.45 мм."""
    me = bpy.data.meshes.new("grip_ribs")
    tb = bmesh.new()
    for z0, z1, _d in GROOVES:
        span = z0 - z1
        z = z0 - 0.2 * span
        while z >= z1 + 0.2 * span - 0.01:
            half = RIB_SPAN * HALF_W(z)
            arc = _front_arc(z, half)
            rows = []
            for x, y, nx, ny, e in arc:
                h = RIB_H if e < 0.75 else RIB_H - (RIB_H + 0.1) * _smooth(0.75, 1.0, e)
                q = []
                for off, dz in ((-0.45, -RIB_HALF), (-0.45, RIB_HALF), (h, RIB_HALF * 0.6), (h, -RIB_HALF * 0.6)):
                    q.append(tb.verts.new(v(x + nx * off, y + ny * off, z + dz)))
                rows.append(q)
            tb.faces.new(rows[0])
            tb.faces.new(list(reversed(rows[-1])))
            for r0, r1 in zip(rows, rows[1:]):
                for k in range(4):
                    k2 = (k + 1) % 4
                    tb.faces.new((r0[k], r0[k2], r1[k2], r1[k]))
            z -= RIB_PITCH
    bmesh.ops.recalc_face_normals(tb, faces=tb.faces)
    tb.to_mesh(me); tb.free()
    o = bpy.data.objects.new("grip_ribs", me)
    G.objects.link(o)
    o.data.materials.append(material("Polymer"))
    for p in o.data.polygons:
        p.use_smooth = False
    return o


def build(ctx):
    G = ctx["coll"]["Grip"]
    o = {}
    me = bpy.data.meshes.new("Pistol_grip")
    bm = bmesh.new()
    rings = []
    z = Z_RING_TOP
    while z >= Z_BOTTOM - 1e-6:
        rings.append([bm.verts.new(v(*p)) for p in ring(z)])
        z -= DZ
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
    # срез: дно — перпендикулярно оси рукояти через конец оси; верх — площадка под ресивером (без подъёма за ним)
    a = axis_pt(1.0)
    p0, p1 = a + FWD * 120.0, a - FWD * 120.0
    top = [(p1.x, GRIP_TOP_Z), (p0.x, GRIP_TOP_Z)]
    clip = prism_xz("grip_clip", [(p0.x, p0.z), (p1.x, p1.z)] + top, -60, 60, G)
    boolean(grip, clip, "INTERSECT")
    # плоскость шва со стойкой скобы и низом ресивера над ней: срезаем всё, что впереди, от площадки до конца перехода
    # выступа в выемку под средний палец — шов ровный, без клиновых пустот по краям
    from lib import box
    boolean(grip, box("cut_lug_seam", GUARD_POST_X - LUG_SEAM, -60.0, -40.0, 40.0, LUG_Z - 9.5, GRIP_TOP_Z + 4.0, G))
    # отверстие под винт снизу: ось винта параллельна оси рукояти и выходит на площадку под отверстием ресивера (x −158.6)
    bottom = axis_pt(1.0) + FWD * SCREW_OFF
    # канал под ключ снизу до головки винта и проход стержня через верх рукояти в ресивер
    hole = lathe("cut_grip_screw", [(-1.0, 0.0), (-1.0, 5.2), (U_TOP - SCREW_HEAD_D + 4.05, 5.2), (U_TOP - SCREW_HEAD_D + 4.05, 3.3),
                                    (U_TOP + 1.5, 3.3), (U_TOP + 1.5, 0.0)], G, None, seg=40, cy=0.0, cz=0.0)
    hole.rotation_euler = (0, math.radians(-90 + ANGLE), 0)
    hole.location = v(bottom.x, 0, bottom.z)
    apply_transform(hole)
    boolean(grip, hole)
    # кромки площадки и дна скруглены (дно — шире: за него берутся)
    finish(grip, w=1.2, seg=4, angle=40)
    # утопленные площадки текстуры по бокам (срез по поверхности рукояти на PANEL_DEPTH)
    for s_ in (-1, 1):
        boolean(grip, panel_cutter(s_, G))
    finish(grip, w=0.3, seg=2, angle=40)
    for p in grip.data.polygons:
        p.use_smooth = True
    # бугорки на дне площадок и рёбрышки в выемках — замкнутые тела, основания утоплены в поверхность
    tex = stipple(G)
    rb = ribs(G)
    grip = join([grip, tex, rb], "Pistol_grip")
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
