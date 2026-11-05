# «Осока»: пусковой механизм ПМ-52 (по образцу 9П521) — литой корпус под трубой, спусковая коробка, рукоять с
# насечённой вставкой, спуск, рычаг «ИСХОДНОЕ — НАКОЛ» (накол источника питания), кнопка в резиновом колпачке,
# накладка с винтами, ушки с винтами, короб электроники (верх, задняя накладка, низ, защёлки), табличка «ПМ-52 №»
# со штампом, толкатель за рукоятью. Ширины — оценка (dims.py); контуры — снимок КБМ.
import math
import bmesh
import bpy
from mathutils import Matrix, Vector
from lib import (MM, v, lathe, rounded_prism, finish, finish_small, fillet, px, px_x, px_z, cyl, boolean, set_origin,
                 join, apply_transform, smooth_poly)
import dims as D
import stamps

CAST_LEFT = D.CAST_Y[1]


def P(pts):
    return [px(x, y) for x, y in pts]


def slotted_screw(name, center, normal, d, coll, mat="Steel_black", slot_ang=0.0):
    """Винт с полукруглой головкой и шлицем: center — точка на поверхности (мм), normal — наружу (ось ±X/±Y/±Z)."""
    r = d / 2
    h = r * 0.55
    prof = [(-0.6, 0.0), (-0.6, r), (0.0, r), (h * 0.35, r * 0.93), (h * 0.7, r * 0.72), (h, 0.0)]
    o = lathe(name, prof, coll, mat, seg=32)
    # шлиц — тонкий брусок поперёк головки
    from lib import box
    cut = box("_slot", h * 0.45, h + 1.0, -r - 1.0, r + 1.0, -0.45, 0.45, coll)
    cut.data.transform(Matrix.Rotation(math.radians(slot_ang), 4, "X"))
    boolean(o, cut)
    n = Vector(normal).normalized()
    rot = Vector((1, 0, 0)).rotation_difference(n).to_matrix().to_4x4()
    o.data.transform(rot)
    o.data.transform(Matrix.Translation(Vector(center) * MM))
    return o


def cast_body(coll):
    pts = fillet(P(D.CAST_PX), [3.0, 4.0, 5.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0], seg=5)
    o = rounded_prism("Launcher_cast", pts, D.CAST_Y[0], D.CAST_Y[1], 2.6, coll, "Paint_olive_cast")
    # боковины — мелкой сеткой до обжатия по трубе (большие многоугольники показывались клиньями и точками у кромки)
    from lib import grid_split
    grid_split(o, step=4.0)
    return o


def grip(coll):
    """Спусковая рама и рукоять — одно литьё (v02, снимок КБМ крупно): передняя стенка с пазом под спуск, рукоять с
    утопленной вставкой и ромбической насечкой, низ рамы до короба. Рама симметрична: паз и вставка режутся слева,
    правая половина — отражением."""
    from lib import boolean_safe, prism_xz
    pts = fillet(P(D.FRAME_PX), [4.6] * len(D.FRAME_PX), seg=5)
    o = rounded_prism("Launcher_grip", pts, D.FRAME_Y[0], D.FRAME_Y[1], 4.0, coll, "Paint_olive_cast")
    # плоские боковины — мелкой сеткой ДО вырезов (простые многоугольники без дыр режутся надёжно): иначе после паза и
    # вставки боковина — многоугольник на 280 вершин, показ давал тёмные клинья-«пилу» (владелец о v04–v05)
    from lib import grid_split
    grid_split(o, step=3.0)
    # паз под спуск: от передней стенки внутрь за ось спуска
    slot = fillet(P([(550, 588), (596, 588), (603, 600), (603, 632), (550, 632)]), [1.5] * 5, seg=3)
    c = prism_xz("_trig_slot", slot, -3.9, 3.9, coll)
    boolean_safe(o, c, name="trigger_slot")
    pp = fillet(P(D.FRAME_PANEL_PX), [4.2] * len(D.FRAME_PANEL_PX), seg=5)
    # вставки — вычитанием с обеих сторон (отражение половины оставляло по средней плоскости несваренный пилообразный
    # шов, v03); задвоенные грани после вычитания справа — убрать
    for side, (y0, y1) in (("L", (D.FRAME_Y[1] - 0.8, D.FRAME_Y[1] + 3.0)), ("R", (D.FRAME_Y[0] - 3.0, D.FRAME_Y[0] + 0.8))):
        c = rounded_prism("_panel_" + side, pp, y0, y1, 0.5, coll)
        boolean_safe(o, c, name="grip_panel_" + side)
        drop_dup_faces(o)
    # упор пальца — после паза, вставки и отражения (булевы по чистой сетке), насечка — последней
    finger_spur(o, coll)
    for side in (1, -1):
        knurl_patch(o, pp, side * (D.FRAME_Y[1] - 0.8), side, coll)
    return [o]


def drop_dup_faces(o):
    """Убрать задвоенные грани (тот же набор вершин) — след точного булева на симметричной детали."""
    bm = bmesh.new(); bm.from_mesh(o.data)
    seen = {}
    dup = []
    for f in bm.faces:
        k = tuple(sorted(v.index for v in f.verts))
        if k in seen:
            dup.append(f)
        else:
            seen[k] = f
    if dup:
        bmesh.ops.delete(bm, geom=dup, context="FACES_ONLY")
        bm.to_mesh(o.data)
        print("DUP_FACES_DROPPED", o.name, len(dup))
    bm.free()


def finger_spur(grip_o, coll):
    """Упор пальца — прилив литья рукояти (v02.1, владелец: «как будто на соплю приделан» — была отдельная пластина
    8 мм): сужается от корня к носику 5 × 3.6 мм; у грани рукояти корень расширяется до 19 × 15 (в пределах плоской части грани) — переход без ступеньки
    (скругление стыка фаской давало рваный край)."""
    from lib import loft_yz, boolean_safe, bevel_edges
    xr, zr = px_x(597.0), px_z(597, 646)            # корень на передней грани рукояти
    xt, zt = px_x(578.0), px_z(578, 648.5)          # носик
    secs = []

    def sec(w, h, p=3.0, n=28):
        out = []
        for k in range(n):
            a = 2 * math.pi * k / n
            c, s = math.cos(a), math.sin(a)
            out.append((0.5 * w * math.copysign(abs(c) ** (2 / p), c), 0.5 * h * math.copysign(abs(s) ** (2 / p), s)))
        return out

    # корень расширяется к грани рукояти (как литейная галтель): поверхность ложится на грань под малым углом
    L = xt - xr
    for x, w, h in ((xr - 4.0, 19.0, 15.0), (xr - 0.6, 19.0, 15.0), (xr + 0.4, 16.6, 12.6), (xr + 1.4, 14.6, 10.6),
                    (xr + 2.8, 13.2, 9.2), (xr + 0.35 * L, 10.4, 7.3), (xr + 0.62 * L, 7.8, 5.5),
                    (xr + 0.85 * L, 5.9, 4.2), (xt, 5.0, 3.6), (xt + 0.9, 3.9, 2.8), (xt + 1.5, 2.2, 1.6),
                    (xt + 1.75, 0.6, 0.45)):
        f = min(max((x - xr) / (xt - xr), 0.0), 1.0)
        zc = zr + (zt - zr) * f
        secs.append((x, [(y, zc + z) for y, z in sec(w, h)]))
    sp = loft_yz("_spur", secs, coll, "Paint_olive_cast")
    print("SPUR_UNION", boolean_safe(grip_o, sp, op="UNION", name="finger_spur"))


def frame_details(coll):
    """Рычажок спусковой рамы слева (серебристые оси), ползунок переключателя в рамке и рычажок с винтом справа."""
    out = []
    (ax, ay, ad), (bx, by, bd), (cx, cy, cd) = D.FRAME_LEVER_PX
    A = Vector(px(ax, ay)); B = Vector(px(bx, by))
    d = (B - A).normalized(); n = Vector((-d.y, d.x))
    arm = [tuple(A - n * 4.2 - d * 3.0), tuple(B - n * 4.2 + d * 3.0), tuple(B + n * 4.2 + d * 3.0), tuple(A + n * 4.2 - d * 3.0)]
    arm = fillet(arm, [3.8] * 4, seg=4)
    out.append(rounded_prism("Frame_lever", arm, CAST_LEFT - 0.4, CAST_LEFT + 2.6, 0.8, coll, "Paint_olive_cast"))
    for i, (x, y, dd) in enumerate(((ax, ay, ad), (bx, by, bd), (cx, cy, cd))):
        out.append(cyl(f"Frame_lever_pivot_{i}", CAST_LEFT + 1.5, CAST_LEFT + 4.2, dd / 2, coll, "Steel_bare", seg=32,
                       cy=px_x(x), cz=px_z(x, y), axis="Y", ch=0.6))
    # справа: ползунок в рамке (снимок 05)
    x0, x1, y0, y1 = D.SLIDER_PX
    X0, X1 = px_x(x1), px_x(x0)
    Z0, Z1 = px_z(625, y1), px_z(625, y0)
    yf = D.FRAME_Y[0]
    rim = fillet([(X0, Z0), (X1, Z0), (X1, Z1), (X0, Z1)], [2.2] * 4, seg=4)
    frame = rounded_prism("Slider_frame", rim, yf - 2.0, yf + 0.6, 0.6, coll, "Paint_olive_cast")
    from lib import prism_xz, boolean_safe
    win = prism_xz("_slider_win", fillet([(X0 + 3.0, Z0 + 3.0), (X1 - 3.0, Z0 + 3.0), (X1 - 3.0, Z1 - 3.0),
                                          (X0 + 3.0, Z1 - 3.0)], [1.2] * 4, seg=3), yf - 3.0, yf - 0.6, coll)
    boolean_safe(frame, win, name="slider_window")
    kx = X0 + 0.32 * (X1 - X0)
    knob = rounded_prism("Slider_knob", fillet([(kx - 3.0, Z0 + 3.6), (kx + 3.0, Z0 + 3.6), (kx + 3.0, Z1 - 3.6),
                                                (kx - 3.0, Z1 - 3.6)], [1.0] * 4, seg=3), yf - 4.2, yf - 0.4, 0.9, coll,
                         "Plastic_black")
    out += [frame, knob]
    # справа спереди: рычажок с винтом на литье
    L0, L1 = Vector(px(558, 566)), Vector(px(592, 576))
    d = (L1 - L0).normalized(); n = Vector((-d.y, d.x))
    pl = fillet([tuple(L0 - n * 3.5), tuple(L1 - n * 2.6), tuple(L1 + n * 2.6), tuple(L0 + n * 3.5)], [2.4] * 4, seg=4)
    out.append(rounded_prism("Right_lever", pl, D.CAST_Y[0] - 2.4, D.CAST_Y[0] + 0.4, 0.7, coll, "Paint_olive_cast"))
    out.append(slotted_screw("Right_lever_screw", (L0.x + 1.0, D.CAST_Y[0] - 2.4, L0.y), (0, -1, 0), 5.0, coll, "Steel_bare"))
    return out


def knurl_patch(target, poly, y_plane, side, coll, pitch=1.6, h=0.5, inset=0.6):
    """Ромбическая насечка в плоскости XZ на y_plane (side — куда наружу): сетка по диагональным осям, пирамидки,
    грани внутри контура poly (отступ inset); вливается в сетку рукояти — часть детали."""
    from mathutils.geometry import intersect_point_line
    xs = [p[0] for p in poly]; zs = [p[1] for p in poly]

    def inside(x, z, d):
        # точка внутри многоугольника и не ближе d к краю
        c = False
        n = len(poly)
        for i in range(n):
            x1, z1 = poly[i]; x2, z2 = poly[(i + 1) % n]
            if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1 + 1e-12) + x1:
                c = not c
        if not c:
            return False
        for i in range(n):
            a = Vector((poly[i][0], poly[i][1])); b = Vector((poly[(i + 1) % n][0], poly[(i + 1) % n][1]))
            q, f = intersect_point_line(Vector((x, z)), a, b)
            f = min(max(f, 0.0), 1.0)
            if (a + (b - a) * f - Vector((x, z))).length < d:
                return False
        return True

    # пирамидки: ячейки сетки по диагональным осям (ромбы), углы ячеек — впадины, центр — вершина (4 треугольника)
    e1 = Vector((1.0, 1.0)).normalized() * pitch
    e2 = Vector((-1.0, 1.0)).normalized() * pitch
    cx0, cz0 = 0.5 * (min(xs) + max(xs)), 0.5 * (min(zs) + max(zs))
    o2 = Vector((cx0, cz0))
    span = int(max(max(xs) - min(xs), max(zs) - min(zs)) / pitch) + 3
    bm = bmesh.new()
    corners = {}

    def corner(i, k):
        if (i, k) not in corners:
            q = o2 + e1 * i + e2 * k
            corners[(i, k)] = bm.verts.new(v(q.x, y_plane, q.y))
        return corners[(i, k)]

    for i in range(-span, span):
        for k in range(-span, span):
            c = o2 + e1 * (i + 0.5) + e2 * (k + 0.5)
            if not inside(c.x, c.y, inset + pitch * 0.75):
                continue
            pk = bm.verts.new(v(c.x, y_plane + side * h, c.y))
            ring = [corner(i, k), corner(i + 1, k), corner(i + 1, k + 1), corner(i, k + 1)]
            for j in range(4):
                tri = (ring[j], ring[(j + 1) % 4], pk)
                bm.faces.new(tri if side > 0 else tuple(reversed(tri)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # нормали — наружу (side): у плоского лоскута recalc может развернуть — проверим по первой грани
    if bm.faces:
        bm.faces.ensure_lookup_table()
        f0 = bm.faces[0]
        f0.normal_update()
        if f0.normal.y * side < 0:
            for f in bm.faces:
                f.normal_flip()
    me = bpy.data.meshes.new("_knurl"); bm.to_mesh(me); bm.free()
    bm = bmesh.new(); bm.from_mesh(target.data); bm.from_mesh(me); bm.to_mesh(target.data); bm.free()
    bpy.data.meshes.remove(me)


def trigger(coll):
    """Спуск — изогнутое перо с задним приливом на оси в пазу рамы (снимок КБМ: ось 585, 606)."""
    pts = fillet(P(D.TRIGGER2_PX), [1.3] * len(D.TRIGGER2_PX), seg=4)
    o = rounded_prism("Trigger", pts, -3.0, 3.0, 1.0, coll, "Steel_bare")
    pv = D.TRIGGER2_PIVOT_PX
    set_origin(o, (px_x(pv[0]), 0.0, px_z(*pv)))
    pin = cyl("Trigger_pin", -D.FRAME_Y[1] - 0.6, D.FRAME_Y[1] + 0.6, 1.6, coll, "Steel_bare", seg=24,
              cy=px_x(pv[0]), cz=px_z(*pv), axis="Y", ch=0.3)
    return o, pin


def lever(coll):
    """Рычаг «ИСХОДНОЕ — НАКОЛ»: ось спереди у горловины источника питания, рукоятка с головкой назад-вверх (v05);
    поворот вокруг Y."""
    px0, pz0 = px_x(D.LEVER_PIVOT_PX[0]), px_z(*D.LEVER_PIVOT_PX)
    tx, tz = px_x(D.LEVER_TIP_PX[0]), px_z(*D.LEVER_TIP_PX)
    d = Vector((tx - px0, tz - pz0))
    L = d.length
    n = Vector((-d.y, d.x)).normalized()
    hw1 = 3.4
    # контур: полукруглая головка оси R 6 позади оси, плечо сужается к рукоятке (полуширина 3.4)
    u = d / L
    pts = []
    for k in range(17):
        a = math.pi / 2 + math.pi * k / 16
        p = Vector((px0, pz0)) + u * (6.0 * math.cos(a)) + n * (6.0 * math.sin(a))
        pts.append((p.x, p.y))
    p_end1 = Vector((tx, tz)) - n * hw1
    p_end2 = Vector((tx, tz)) + n * hw1
    pts += [(p_end1.x, p_end1.y), (p_end2.x, p_end2.y)]
    pts = fillet(pts, [1.6] * len(pts), seg=3)
    # плечо — над боковиной на 2.8 мм (на высокой бобышке оси): проходит над литыми буквами и бобышками литья
    arm = rounded_prism("Lever_arm", pts, CAST_LEFT + 2.8, CAST_LEFT + 6.8, 1.2, coll, "Paint_olive_cast")
    boss = cyl("Lever_boss", CAST_LEFT - 0.5, CAST_LEFT + 7.6, 6.5, coll, "Paint_olive_cast", seg=40, cy=px0, cz=pz0,
               axis="Y", ch=0.8)
    knob = cyl("Lever_knob", CAST_LEFT + 3.6, CAST_LEFT + 15.6, 5.6, coll, "Paint_olive_cast", seg=40, cy=tx, cz=tz,
               axis="Y", ch=1.6)
    o = join([arm, boss, knob], "Lever")
    set_origin(o, (px0, CAST_LEFT, pz0))
    # шайба оси на корпусе
    ax = cyl("Lever_axle", CAST_LEFT - 1.0, CAST_LEFT + 8.7, 2.4, coll, "Steel_black", seg=24, cy=px0, cz=pz0, axis="Y",
             ch=0.5)
    return o, ax


def linkage(coll):
    """Продольная тяга от оси рычага назад (снимок: 452…546 × 556…560) с винтом на конце."""
    x0, x1 = px_x(546), px_x(452)
    z = px_z(500, 558)
    pts = fillet([(x0, z - 2.6), (x1, z - 2.6), (x1, z + 2.6), (x0, z + 2.6)], [2.4] * 4, seg=4)
    bar = rounded_prism("Lever_linkage", pts, CAST_LEFT - 0.4, CAST_LEFT + 2.2, 0.8, coll, "Paint_olive_cast")
    sc = slotted_screw("Lever_linkage_screw", (x0 + 3.0, CAST_LEFT + 2.2, z), (0, 1, 0), 4.2, coll, "Paint_olive_cast",
                       slot_ang=60)
    return [bar, sc]


def cast_pad(coll):
    """Приподнятая площадка литья (v05): на снимках МАКС-2015 диагональ — левая кромка площадки, не прорезь
    (тонкая канавка v01–v04 выглядела порезом)."""
    pts = fillet(P(D.CAST_PAD_PX), [2.5, 2.5, 1.5, 1.5], seg=4)
    return rounded_prism("Launcher_cast_pad", pts, CAST_LEFT - 0.6, CAST_LEFT + 0.9, 0.7, coll, "Paint_olive_cast")


def cast_bosses(coll):
    """Круглые бобышки литья за рычагом (снимок МАКС-2015): с кольцом и штифтом."""
    out = []
    for i, (x, y, d) in enumerate(D.CAST_BOSSES_PX):
        X, Z = px_x(x), px_z(x, y)
        out.append(cyl(f"Launcher_boss_{i}", CAST_LEFT - 0.5, CAST_LEFT + 2.4, d / 2, coll, "Paint_olive_cast", seg=48,
                       cy=X, cz=Z, axis="Y", ch=0.8))
        out.append(cyl(f"Launcher_boss_pin_{i}", CAST_LEFT + 1.6, CAST_LEFT + 3.4, d * 0.22, coll, "Steel_black", seg=32,
                       cy=X, cz=Z, axis="Y", ch=0.4))
    return out


def button(coll):
    x, y, d = D.BUTTON_PX
    X, Z = px_x(x), px_z(x, y)
    boss = cyl("Button_boss", CAST_LEFT - 1.0, CAST_LEFT + 3.0, d / 2, coll, "Paint_olive_cast", seg=48, cy=X, cz=Z,
               axis="Y", ch=1.0)
    cap = lathe("Button_cap", [(0.0, 0.0), (0.0, 7.6), (1.2, 7.4), (2.6, 6.4), (3.6, 4.4), (4.1, 0.0)], coll,
                "Rubber_black", seg=40)
    cap.data.transform(Matrix.Rotation(math.pi / 2, 4, "Z"))
    cap.data.transform(Matrix.Translation(v(X, CAST_LEFT + 2.6, Z)))
    return [boss, cap]


def cover_plate(coll):
    x0, y0, x1, y1 = 529, 503, 660, 530
    pts = fillet(P([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]), [3.5] * 4, seg=4)
    plate = rounded_prism("Launcher_cover_plate", pts, CAST_LEFT - 0.5, CAST_LEFT + 1.4, 0.7, coll, "Paint_olive_cast")
    screws = []
    for i, (sx, d) in enumerate(((537, 5.0), (584, 7.0), (629, 5.0))):
        screws.append(slotted_screw(f"Launcher_cover_screw_{i}", (px_x(sx), CAST_LEFT + 1.4, px_z(sx, 514.3)),
                                    (0, 1, 0), d, coll, "Paint_olive_cast", slot_ang=0 if i != 1 else 90))
    return [plate] + screws


def tabs(coll):
    """Ушки накладки с винтами по верхней кромке литья (снимок: x 391, 484, 557, 586, 734; y ≈ 482)."""
    out = []
    for i, x in enumerate((391, 484, 557, 586, 734)):
        X = px_x(x)
        # первое ушко над кнопкой — короче, не наезжает на её ободок (v03)
        zt, zb = px_z(x, 466), px_z(x, 484 if i == 0 else 492)
        pts = fillet([(X - 5.5, zb), (X + 5.5, zb), (X + 5.5, zt), (X - 5.5, zt)], [5.0, 5.0, 1.0, 1.0], seg=5)
        t = rounded_prism(f"Launcher_tab_{i}", pts, CAST_LEFT - 0.5, CAST_LEFT + 1.8, 0.7, coll, "Paint_olive_cast")
        s = slotted_screw(f"Launcher_tab_screw_{i}", (X, CAST_LEFT + 1.8, zb + 4.5), (0, 1, 0), 4.6, coll,
                          "Paint_olive_cast", slot_ang=30 * i)
        out += [t, s]
    return out


def plunger(coll):
    x, y, d = D.PLUNGER_PX
    X, Z = px_x(x), px_z(x, y)
    o = cyl("Plunger", D.FRAME_Y[1] - 1.0, D.FRAME_Y[1] + 6.0, d / 2, coll, "Plastic_black", seg=40, cy=X,
            cz=Z, axis="Y", ch=1.8)
    return o


def box(coll):
    up = fillet(P(D.BOX_UPPER_PX), [3.6, 3.6, 4.0, 3.6, 3.6], seg=5)
    upper = rounded_prism("Box_upper", up, D.BOX_Y[0], D.BOX_Y[1], 3.2, coll, "Paint_olive_cast")
    rp = fillet(P(D.BOX_REAR_PLATE_PX), [2.3, 2.3, 2.3, 2.3, 2.3, 2.3], seg=4)
    rear = rounded_prism("Box_rear_plate", rp, D.BOX_Y[0] + 4.0, D.BOX_Y[1] - 4.0, 2.0, coll, "Paint_olive_cast")
    lo = fillet(P(D.BOX_LOWER_PX), [4.5, 4.5, 4.5, 6.0, 6.0, 4.5], seg=5)
    lower = rounded_prism("Box_lower", lo, D.BOX_Y[0] - 0.8, D.BOX_Y[1] + 0.8, 4.2, coll, "Paint_olive_cast")
    # шов крышки — бортик по низу верхней части
    seam_pts = fillet(P([(756, 591), (1049, 591), (1049, 597), (756, 597)]), [1.3] * 4, seg=3)
    seam = rounded_prism("Box_seam_lip", seam_pts, D.BOX_Y[0] - 1.4, D.BOX_Y[1] + 1.4, 1.0, coll, "Paint_olive_cast")
    knuckles = []
    for i, x in enumerate(D.BOX_KNUCKLES_X):
        X = px_x(x)
        for s in (1, -1):
            k = cyl(f"Box_latch_{i}_{'L' if s > 0 else 'R'}", px_z(x, 625), px_z(x, 598), 4.2, coll, "Paint_olive_cast",
                    seg=32, cy=X, cz=s * (D.BOX_Y[1] + 2.6), axis="Z", ch=0.8)
            knuckles.append(k)
    return [upper, rear, lower, seam] + knuckles


def grille(coll):
    """Решётка звукового сигнала на нижнем коробе слева: квадратная накладка на четырёх винтах, круг с вертикальными
    прорезями (макеты «Армия-2016», выставочный образец)."""
    from lib import boolean_safe, prism_xz
    x, y, d = D.GRILLE_PX
    X, Z = px_x(x), px_z(x, y)
    yf = D.BOX_Y[1] + 0.8
    h = d / 2 + 1.0
    plate = rounded_prism("Grille_plate", fillet([(X - h, Z - h), (X + h, Z - h), (X + h, Z + h), (X - h, Z + h)], [7.0] * 4,
                                                  seg=5), yf - 0.6, yf + 1.4, 0.7, coll, "Paint_olive_cast")
    for k in range(-3, 4):
        sx = X + k * 4.6
        hh = math.sqrt(max((d / 2 - 7.0) ** 2 - (k * 4.6) ** 2, 4.0))
        c = prism_xz("_gslot", fillet([(sx - 1.2, Z - hh), (sx + 1.2, Z - hh), (sx + 1.2, Z + hh), (sx - 1.2, Z + hh)],
                                      [1.15] * 4, seg=3), yf - 0.2, yf + 3.0, coll)
        boolean_safe(plate, c, name="grille_slot")
    out = [plate]
    for i, (dx, dz) in enumerate(((-h + 4.5, -h + 4.5), (h - 4.5, -h + 4.5), (-h + 4.5, h - 4.5), (h - 4.5, h - 4.5))):
        out.append(slotted_screw(f"Grille_screw_{i}", (X + dx, yf + 1.4, Z + dz), (0, 1, 0), 3.8, coll, "Paint_olive_cast",
                                 slot_ang=35 * i))
    return out


def nameplate(coll):
    x0, x1, y0, y1 = D.NAMEPLATE_PX
    X0, X1 = px_x(x1), px_x(x0)
    Zt, Zb = px_z(990, y0), px_z(990, y1)
    zc = 0.5 * (Zt + Zb)
    h = Zt - Zb
    pts = fillet([(X0, Zb), (X1, Zb), (X1, Zt), (X0, Zt)], [h / 2 - 0.2] * 4, seg=8)
    y0_, y1_ = D.BOX_Y[1] - 0.3, D.BOX_Y[1] + 0.7
    # плоская призма: штамп по простым граням надёжен (скругление или нарезка до штампа ломали булево); после штампа
    # скругляется только наружный контур (общее скругление «надувало» буквы, v03), кромки букв — острые, лицо —
    # треугольниками (большая грань с дырами-буквами показывалась клиньями)
    from lib import prism_xz, renormal, bevel_edges
    rivets = []
    for i, X in enumerate((X0 + h / 2, X1 - h / 2)):
        r = lathe(f"Nameplate_rivet_{i}", [(-0.3, 0.0), (-0.3, 1.5), (0.0, 1.5), (0.35, 1.3), (0.7, 0.8), (0.85, 0.0)], coll,
                  "Plate_alu", seg=24)
        r.data.transform(Matrix.Rotation(math.pi / 2, 4, "Z"))
        r.data.transform(Matrix.Translation(v(X, y1_, zc)))
        rivets.append(r)
    # штамп: две строки вглубь 0.2 мм. Точное булево изредка не вырезает букву (от запуска к запуску) — тогда табличка
    # собирается заново со сдвигом надписи на сотые миллиметра, пока не встанут все буквы
    xc = 0.5 * (X0 + X1)
    t1, t2 = D.NAMEPLATE_TEXT
    for k in range(8):
        dx, dz = 0.031 * k, -0.023 * k
        plate = prism_xz("Nameplate", pts, y0_, y1_, coll, "Plate_alu")
        n0 = len(stamps.FAILED)
        stamps.stamp(plate, t1, 5.6, (xc + dx, y1_, zc + 2.3 + dz), (0, 1, 0), (0, 0, 1), 0.2, coll)
        stamps.stamp(plate, t2, 4.6, (xc + dx, y1_, zc - 2.5 + dz), (0, 1, 0), (0, 0, 1), 0.2, coll)
        if len(stamps.FAILED) == n0:
            break
        print("NAMEPLATE_RETRY", k)
        del stamps.FAILED[n0:]
        me = plate.data
        bpy.data.objects.remove(plate, do_unlink=True)
        bpy.data.meshes.remove(me)
    else:
        print("NAMEPLATE_FAIL")
    tx0, tx1 = xc - 0.5 * (X1 - X0) + h / 2, xc + 0.5 * (X1 - X0) - h / 2

    def outline(mid):
        # рёбра контура таблички (вне поля надписи или на её торцах и задней грани)
        return not (tx0 < mid.x < tx1 and Zb + 0.6 < mid.z < Zt - 0.6 and mid.y > y1_ - 0.35)
    bevel_edges(plate, lambda a, b: a.angle(b) > math.radians(30), w=0.25, seg=3, where=outline)
    bm = bmesh.new(); bm.from_mesh(plate.data)
    big = [f for f in bm.faces if len(f.verts) > 4]
    bmesh.ops.triangulate(bm, faces=big, quad_method="BEAUTY", ngon_method="EAR_CLIP")
    bm.to_mesh(plate.data); bm.free()
    renormal(plate)
    return [plate] + rivets


def labels(target, coll):
    from lib import grid_split_local
    for text, x, y, size in D.LABELS:
        # большая многоугольная боковина литья: точное булево пропускало буквы — режем её мелко вокруг надписи
        grid_split_local(target, (px_x(x), CAST_LEFT, px_z(x, y)), size * len(text) * 0.4 + 3.0, (0, 2), step=1.37)
        stamps.stamp(target, text, size, (px_x(x), CAST_LEFT, px_z(x, y)), (0, 1, 0), (0, 0, 1), 0.35, coll, raised=True)


def build(ctx):
    C = ctx["coll"]["Launcher"]
    cast = cast_body(C)
    from lib import hug_tube
    print("HUG Launcher_cast", hug_tube(cast))
    labels(cast, C)
    cast_pad(C)
    cast_bosses(C)
    g = grip(C)
    fd = frame_details(C)
    trig, tpin = trigger(C)
    lv, lax = lever(C)
    btn = button(C)
    cp = cover_plate(C)
    tb = tabs(C)
    pl = plunger(C)
    bx = box(C)
    gr = grille(C)
    npl = nameplate(C)
    return {"trigger": trig, "lever": lv, "plunger": pl, "button_cap": btn[1]}
