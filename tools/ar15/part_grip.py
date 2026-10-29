# AR-15: пистолетная рукоять, эргономичная (владелец, 2026-10-29: «рукоятка слишком примитивная и без нужных изгибов» —
# по образцам: рукоять STM-416 на снимке владельца и рукоять AR15 Lokeig на Sketchfab). За рукоятью — выемка под
# перепонку между большим и указательным пальцами: окружность lib.SEAM_ARC_R, самая глубокая точка на шве с ресивером;
# ниже шва спинка идёт по той же дуге до касания и дальше прямой под углом рукояти до дна (владелец 29.10: «задняя линия
# рукоятки прямая и стремится к окружности по касательной», ширину рукояти можно уменьшить — выпуклости под ладонь и
# расширения пятки нет); сечение верха — как у ресивера над ним, между ними только тонкий шов. Спереди сверху — выступ
# вперёд до задней стойки скобы, шов с ней вертикальный (владелец, по образцу); ниже выступа — три выемки под средний,
# безымянный палец и мизинец с поперечными рёбрышками внутри; по бокам — утопленные площадки с точечной текстурой.
# Тело — сечения по горизонтали (z) от площадки под ресивером вниз, дно — срез перпендикулярно оси рукояти (18°).
# Винт рукояти — снизу параллельно её оси, в отверстие ресивера (lib.GRIP_SCREW_X на площадке).
import math
import bmesh
import bpy
from mathutils import Vector
from lib import (MM, GRIP_TOP_Z, GRIP_SEAM_BACK_X, GRIP_SCREW_X, SEAM_ARC_R, REAR_PLAN_R, v, pchip as _pchip, prism_xz, prism_yz, lathe, boolean, finish, auto_sharp, apply_transform, join, material)

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
Z_RING_TOP = -37.0              # верхнее сечение: выше площадки, срезается по ней
TOP_BLEND = (GRIP_TOP_Z - 2.0, GRIP_TOP_Z - 16.0)   # сверху сечение — как низ ресивера, ниже плавно в суперэллипс
FRONT_PLAN_R = 2.0              # скругление передних углов того же сечения (перёд всё равно срезан швом со стойкой)
DZ = 0.5                        # шаг сечений
N_RING = 128
P_FRONT, P_BACK = 2.7, 2.4      # «квадратность» передней и задней половин сечения
P_LUG = 6.0                     # у выступа перёд площе: после среза плоскость шва идёт на всю ширину низа ресивера


def _smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# спинка (по средней плоскости): дуга выемки от шва до касания прямой под углом рукояти, дальше прямая до дна
BACK_ARC_C = (GRIP_SEAM_BACK_X - SEAM_ARC_R, GRIP_TOP_Z)                        # середина окружности выемки
BACK_TAN = (BACK_ARC_C[0] + SEAM_ARC_R * CA, GRIP_TOP_Z - SEAM_ARC_R * SA)      # точка касания прямой спинки
# полуширина: у площадки — как у нижнего ресивера (±12.2, бока заподлицо, между ними только шов; владелец 29.10:
# «обрати внимание на форму и толщину» — рукоять была шире ресивера на 2.4 мм с каждой стороны), ниже плавно
# расширяется до 14.7 под ладонью, внизу 16.4
HALF_W = _pchip([(-42.0, 12.2), (-48.0, 12.5), (-56.0, 13.4), (-66.0, 14.3), (-80.0, 15.0), (-100.0, 15.6), (-118.0, 15.4),
                 (-134.0, 15.6), (-142.0, 16.4), (-160.0, 16.4)])


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
    if z >= GRIP_TOP_Z:
        return GRIP_SEAM_BACK_X
    if z >= BACK_TAN[1]:
        return BACK_ARC_C[0] + math.sqrt(SEAM_ARC_R ** 2 - (z - GRIP_TOP_Z) ** 2)
    return BACK_TAN[0] - (BACK_TAN[1] - z) * SLOPE


def front_xz(t, gap=0.0):
    """Передняя кромка рукояти по средней плоскости (мм), сдвинутая вперёд на gap — по ней идёт задняя грань скобы.
    t — параметр по высоте: z = −49.4 − 98.9·t (убывает с t; −0.08 → над площадкой, 0.3775 → ниже перекладины скобы)."""
    z = -49.4 - 98.9 * t
    x = front_x(z)
    return x + FWD.x * gap, z + FWD.z * gap


def _taper(x, z):
    """Прежнее местное сужение верха спинки до ширины ресивера — теперь весь верх рукояти по ширине ресивера (HALF_W)."""
    return 1.0


def section(z):
    xb, xf = back_x(z), front_x(z)
    return xb, xf, HALF_W(z)


def _rrect_reach(hx, w, dx, dy):
    """Расстояние от середины сечения до прямоугольника 2hx × 2w со скруглёнными углами (сзади REAR_PLAN_R, спереди
    FRONT_PLAN_R) по единичному направлению (dx, dy) — тот же контур, что у низа ресивера над рукоятью."""
    def sdf(px, py):
        r = REAR_PLAN_R if px < 0 else FRONT_PLAN_R
        qx, qy = abs(px) - (hx - r), abs(py) - (w - r)
        return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - r
    lo, hi = 0.0, hx + w + 5.0
    for _ in range(48):
        mid = (lo + hi) / 2
        if sdf(mid * dx, mid * dy) < 0.0:
            lo = mid
        else:
            hi = mid
    return lo


def ring(z, n=N_RING):
    xb, xf, w = section(z)
    c, hx = (xf + xb) / 2, (xf - xb) / 2
    wt = 1.0 - _smooth(TOP_BLEND[0], TOP_BLEND[1], z)     # 1 — сечение как у ресивера, 0 — суперэллипс
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        ca, sa = math.cos(a), math.sin(a)
        p = p_front(z) if ca >= 0 else P_BACK
        x = c + hx * math.copysign(abs(ca) ** (2 / p), ca)
        y = w * math.copysign(abs(sa) ** (2 / p), sa) * _taper(x, z)
        if wt > 0.0:
            # тот же луч из середины до контура низа ресивера — точки сдвигаются вдоль него, порядок сохраняется
            dx, dy = x - c, y
            ln = math.hypot(dx, dy)
            reach = _rrect_reach(hx, w, dx / ln, dy / ln)
            x += (c + dx / ln * reach - x) * wt
            y += (dy / ln * reach - y) * wt
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
SCREW_OFF = (GRIP_SCREW_X - TOP_CX) * CA   # смещение оси винта от оси рукояти (назад) — выход на площадку в GRIP_SCREW_X
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
    # кромки площадки и дна скруглены (дно — шире: за него берутся); отверстие — после широкой фаски, иначе фаски края
    # и отверстия сходились на узкой перемычке и дно выходило неплоским (радиальные полосы)
    import lib
    # кромка площадки — узкая (шов с ресивером тонкий, без канавки); три сегмента по 30° широкая фаска уже не берёт
    lib.bevel_edges(grip, lambda n1, n2: n1.z > 0.9 and n2.z < 0.9, w=lib.SEAM_EDGE, seg=3,
                    where=lambda p: p.z > GRIP_TOP_Z - 0.5)
    finish(grip, w=1.8 / lib.ROUND_K, seg=4, angle=40)
    boolean(grip, hole)
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
    # плоский торец с отверстием — плоское затенение: сглаженные нормали на большой грани давали радиальные полосы
    nb = Vector((FWD.z, 0.0, -FWD.x)).normalized()
    if nb.z > 0:
        nb = -nb
    for p in grip.data.polygons:
        if p.normal.dot(nb) > 0.995:
            p.use_smooth = False
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
