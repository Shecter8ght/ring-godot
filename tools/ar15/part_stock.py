# AR-15: буферная трубка mil-spec carbine с направляющей и шестью отверстиями фиксатора, торцевая пластина с гнездом QD,
# замковая гайка, буфер и возвратная пружина внутри, приклад в стиле SL (корпус-клин со скелетной нижней тягой,
# резиновый затыльник с рёбрами, гнёзда QD, прорезь антабки, рычаг фиксатора снизу, литой знак «ГРАНЬ» на боках).
# Ширина по затыльнику 43.2 мм (Magpul MOE SL-M — 1.7″ по двум магазинам; форма своя).
# Приклад в положении «сложен»: передний торец втулки x = STOCK_FRONT; выдвигается назад на STOCK_TRAVEL (5 шагов).
import math
import bpy
from mathutils import Matrix, Vector
from lib import (MM, TUBE_X, BUFFER_R, STOCK_TRAVEL, UPPER_REAR, LOWER_REAR, fillet, arc_pts, prism_xz, prism_yz,
                 prism_xy, loft_yz, box, cyl, lathe, boolean, finish, auto_sharp, apply_transform, set_parent, set_origin,
                 join, material, renormal)
from part_upper import coil

TUBE_R = BUFFER_R                 # Ø29.16
TUBE_IN_R = 12.7                  # Ø1.0″ внутри
TUBE_FRONT = TUBE_X[1] - 0.05     # −176: торец в башне (на 0.05 мм от плоскости — без совпадающих граней)
TUBE_REAR = TUBE_X[0]             # −358
RIDGE_HALF_W = 4.9                # направляющая снизу трубки
RIDGE_Z = -18.0                   # низ направляющей
PLATE_X = (-189.8, -186.6)        # торцевая пластина
HUB_X = (-186.6, -182.05)         # её ступица до башни
NUT_X = (-200.5, PLATE_X[0])      # замковая гайка
NUT_R = 17.4
QD_PLATE = (-191.0, -26.0)        # гнездо QD пластины (x, z), ось вдоль Y
BUF_FRONT = UPPER_REAR - 1.0      # передний торец буфера в положении «заперто»
BUF_BODY_REAR = -234.0
BUF_STEM_REAR = -259.0
STOCK_FRONT = -213.0              # передний торец втулки приклада (сложен)
STOCK_LEN = 150.0                 # корпус без затыльника
PAD_T = 15.0                      # затыльник
STEP = STOCK_TRAVEL / 5.0
PIN_X0 = STOCK_FRONT - 52.0       # фиксатор приклада (сложен) = первое отверстие направляющей
LATCH_PIVOT = (STOCK_FRONT - 11.0, -23.2)
LATCH_DEG = 6.0                   # ход рычага; штифт опускается на ≈ 41·sin(6°) = 4.3 мм
QD_R = 4.85                       # отверстие стандартного антабочного QD (0.38″)
BODY_HW = 20.0                    # полуширина корпуса сзади
BUTT_HW = 20.8                    # задняя стойка
PAD_HW = 21.6                     # затыльник: ширина приклада 43.2
LOGO = "ГРАНЬ"


def superellipse(hw, ztop, zbot, n=40, p=3.2, y0=0.0):
    zc = (ztop + zbot) / 2
    hh = (ztop - zbot) / 2
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        c, s = math.cos(a), math.sin(a)
        y = y0 + hw * math.copysign(abs(c) ** (2 / p), c)
        z = zc + hh * math.copysign(abs(s) ** (2 / p), s)
        pts.append((y, z))
    return pts


def text_mesh(text, size_mm, depth_mm, coll, name="_txt"):
    """Текст замкнутым телом: плоская заливка шрифта, слияние вершин, выдавливание граней на depth_mm от z=0 вверх
    (сетка текста Blender с толщиной негерметична у букв с «окнами» — Р, А, Ь — и ломает булевы)."""
    import bmesh
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = text
    cu.size = size_mm * MM
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = 0.0
    cu.fill_mode = "BOTH"
    cu.resolution_u = 5
    o = bpy.data.objects.new(name, cu)
    coll.objects.link(o)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.curves.remove(cu)
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-8, edges=bm.edges)
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    ret = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces) + list(bm.edges) + list(bm.verts))
    vs = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=vs, vec=Vector((0.0, 0.0, depth_mm * MM)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name + "m", me)
    coll.objects.link(ob)
    return ob


def _frame(center, normal, up):
    n = Vector(normal).normalized(); u = Vector(up).normalized(); r = u.cross(n)
    m = Matrix((r, u, n)).transposed().to_4x4()
    m.translation = Vector(center) * MM
    return m, n


def engrave(target, text, size, center, normal, up, depth, coll):
    """Гравировка: текст уходит в деталь на depth от поверхности (центр — на поверхности)."""
    import lib
    if not getattr(lib, "MARKINGS_GEOMETRY", False):
        return
    cut = text_mesh(text, size, depth + 0.6, coll)
    m, n = _frame(center, normal, up)
    m = Matrix.Translation(-n * depth * MM) @ m
    cut.data.transform(target.matrix_world.inverted() @ m)
    boolean(target, cut)


def logo_relief(target, text, size, center, side, height, coll):
    """Литой знак рельефом: буквы выступают на height над боковиной, основание утоплено на 0.4 мм."""
    import lib
    if not getattr(lib, "MARKINGS_GEOMETRY", False):
        return
    t = text_mesh(text, size, height + 0.4, coll)
    normal = (0.0, float(side), 0.0)
    m, n = _frame(center, normal, (0, 0, 1))
    m = Matrix.Translation(-n * 0.4 * MM) @ m
    t.data.transform(target.matrix_world.inverted() @ m)
    boolean(target, t, "UNION")


def side_y(x, z, s, y_max=30.0):
    """Наружная боковина корпуса приклада в точке (x, z): луч снаружи внутрь (мм)."""
    o = bpy.data.objects["Stock_body"]
    inv = o.matrix_world.inverted()
    org = inv @ (Vector((x, s * y_max, z)) * MM)
    d = (inv.to_3x3() @ Vector((0.0, -s, 0.0))).normalized()
    ok, loc, nrm, idx = o.ray_cast(org, d)
    return (o.matrix_world @ loc).y / MM if ok else s * BODY_HW


def build(ctx):
    S = ctx["coll"]["Stock"]
    o = {}
    o.update(tube(S))
    o.update(stock(S))
    return o


def tube(S):
    o = {}
    # трубка: оболочка, закрытый задний торец с отверстием, фаска сзади
    t = lathe("Buffer_tube", [(TUBE_REAR, 0.0), (TUBE_REAR, TUBE_R - 2.2), (TUBE_REAR + 2.2, TUBE_R), (TUBE_FRONT, TUBE_R),
                              (TUBE_FRONT, TUBE_IN_R), (TUBE_REAR + 3.0, TUBE_IN_R), (TUBE_REAR + 3.0, 0.0)],
              S, "Alu_anodized", seg=72)
    # направляющая снизу (за резьбовой частью), с отверстиями фиксатора
    ridge = prism_yz("tube_ridge", fillet([(-RIDGE_HALF_W, RIDGE_Z), (RIDGE_HALF_W, RIDGE_Z), (RIDGE_HALF_W, -11.0),
                                           (-RIDGE_HALF_W, -11.0)], [0.8, 0.8, 0, 0], 3), TUBE_REAR + 1.5, NUT_X[0] - 1.5, S)
    boolean(t, ridge, "UNION")
    boolean(t, cyl("cut_tube_bore2", TUBE_REAR + 3.0, TUBE_FRONT + 1, TUBE_IN_R, S, seg=72))
    for k in range(6):
        xh = PIN_X0 - STEP * k
        boolean(t, cyl(f"cut_tube_hole{k}", RIDGE_Z - 2, -12.0, 2.45, S, seg=20, cy=xh, cz=0.0, axis="Z"))
    # цифры положений приклада на левой грани направляющей (видны, когда приклад выдвинут)
    for k in range(6):
        engrave(t, str(k + 1), 2.6, (PIN_X0 - STEP * k + 5.2, RIDGE_HALF_W, (RIDGE_Z - 11.0) / 2.0), (0, 1, 0), (0, 0, 1), 0.14, S)
    # торцевой вент сзади и резьба спереди (неглубокие канавки под башней и гайкой)
    boolean(t, cyl("cut_tube_vent", TUBE_REAR - 1, TUBE_REAR + 4, 1.6, S, seg=16))
    for k in range(int((TUBE_FRONT - NUT_X[0] + 2) / 1.6)):
        xx = NUT_X[0] - 1.0 + k * 1.6
        if xx > TUBE_FRONT - 0.8:
            break
        boolean(t, lathe("cut_thread", [(xx - 0.6, TUBE_R + 1.0), (xx, TUBE_R - 0.5), (xx + 0.6, TUBE_R + 1.0)], S, None, seg=72,
                         closed=True))
    finish(t, w=0.25, seg=2, angle=40)
    o["tube"] = t
    # ступица и торцевая пластина с нижним приливом и гнездом QD (вдоль Y, с обеих сторон)
    hub = lathe("End_plate", [(HUB_X[0], TUBE_R + 0.1), (HUB_X[0], 18.2), (HUB_X[1] - 0.6, 18.2), (HUB_X[1], 17.6),
                              (HUB_X[1], TUBE_R + 0.1)], S, "Steel_black", seg=72)
    boolean(hub, box("cut_hub_low", HUB_X[0] - 1, HUB_X[1] + 1, -30, 30, -40, -13.6, S))
    plate = prism_yz("end_plate_body", fillet([(-14.0, -33.0), (14.0, -33.0), (19.0, -12.0), (19.0, 12.0), (12.0, 19.0),
                                               (-12.0, 19.0), (-19.0, 12.0), (-19.0, -12.0)], [7.0, 7.0, 6.0, 6.0, 6.0, 6.0, 6.0, 6.0], 6),
                     PLATE_X[0], PLATE_X[1], S, "Steel_black")
    boolean(hub, plate, "UNION")
    qx, qz = QD_PLATE
    boss = cyl("end_plate_qd", -12.5, 12.5, 6.5, S, "Steel_black", seg=40, cy=qx, cz=qz, axis="Y", ch=0.8)
    boolean(hub, boss, "UNION")
    boolean(hub, cyl("cut_plate_bore", HUB_X[0] - 6, HUB_X[1] + 1, TUBE_R + 0.05, S, seg=72))
    boolean(hub, cyl("cut_plate_qd", -20, 20, QD_R, S, seg=32, cy=qx, cz=qz, axis="Y"))
    for s in (-1, 1):
        y0, y1 = (11.6, 14.0) if s > 0 else (-14.0, -11.6)
        boolean(hub, cyl(f"cut_plate_qd_cb{s}", y0, y1, 5.7, S, seg=32, cy=qx, cz=qz, axis="Y"))
    # кернение — две лунки у кромки гайки (гайка застопорена)
    for a in (-60.0, -120.0):
        yy, zz = 18.1 * math.cos(math.radians(a)), 18.1 * math.sin(math.radians(a))
        d = lathe("stake", [(PLATE_X[0] - 1.0, 0.0), (PLATE_X[0] - 1.0, 0.9), (PLATE_X[0] + 0.6, 0.0)], S, None, seg=16, cy=yy, cz=zz)
        boolean(hub, d)
    finish(hub, w=0.3, seg=2, angle=35)
    o["end_plate"] = hub
    # замковая гайка с тремя прорезями сзади и двумя «пазами» под ключ
    nut = lathe("Castle_nut", [(NUT_X[0], TUBE_R + 0.05), (NUT_X[0], NUT_R - 0.8), (NUT_X[0] + 0.8, NUT_R), (NUT_X[1] - 0.6, NUT_R),
                               (NUT_X[1], NUT_R - 0.6), (NUT_X[1], TUBE_R + 0.05)], S, "Steel_black", seg=72)
    for k in range(3):
        a = 90.0 + 120.0 * k
        c = box("cut_nut_slot", NUT_X[0] - 1, NUT_X[0] + 3.3, -2.3, 2.3, 10.0, 22.0, S)
        c.rotation_euler = (math.radians(a - 90.0), 0, 0)
        apply_transform(c)
        boolean(nut, c)
    finish(nut, w=0.3, seg=2, angle=35)
    o["castle_nut"] = nut
    # буфер: резиновый бампер спереди, корпус, хвостовик под пружину; грузы внутри не моделируются
    buf = lathe("Buffer", [(BUF_STEM_REAR, 0.0), (BUF_STEM_REAR, 7.4), (BUF_STEM_REAR + 0.8, 8.1), (BUF_BODY_REAR - 1.0, 8.1),
                           (BUF_BODY_REAR, 9.0), (BUF_BODY_REAR, 11.6), (BUF_BODY_REAR + 1.0, 12.2), (BUF_FRONT - 5.5, 12.2),
                           (BUF_FRONT - 4.5, 11.2), (BUF_FRONT - 4.5, 0.0)], S, "Steel_black", seg=48)
    finish(buf, w=0.3, seg=2, angle=35)
    o["buffer"] = buf
    bump = lathe("Buffer_bumper", [(BUF_FRONT - 4.6, 0.0), (BUF_FRONT - 4.6, 10.6), (BUF_FRONT - 1.8, 10.6), (BUF_FRONT - 0.6, 9.4),
                                   (BUF_FRONT, 6.0), (BUF_FRONT, 0.0)], S, "Polymer", seg=48)
    o["buffer_bumper"] = bump
    set_origin(buf, (BUF_FRONT, 0.0, 0.0))
    set_parent(bump, buf)
    # возвратная пружина: от упора буфера до заднего торца трубки внутри; начало координат — у заднего торца
    x_rear = TUBE_REAR + 3.0
    x_front = BUF_BODY_REAR - 0.5
    spr = coil("Buffer_spring", x_rear + 0.95, x_front - 0.95, 9.9, 0.95, 28, S, cy=0.0, cz=0.0, seg=10)
    set_origin(spr, (x_rear, 0.0, 0.0))
    o["buffer_spring"] = spr
    return o


def stock(S):
    o = {}
    F = STOCK_FRONT
    R = F - STOCK_LEN                     # задний торец корпуса (перед затыльником)
    top_f, top_r = 19.5, 21.5
    bot = -23.6
    # --- втулка вокруг трубки: скруглённый верх, плоские бока ---
    secs = []
    for x, hw, zt, zb in ((F, 17.6, top_f - 1.6, bot + 1.6), (F - 1.2, 18.8, top_f - 0.4, bot + 0.4), (F - 3.0, 19.3, top_f, bot),
                          (F - 60.0, 19.6, top_f + 0.8, bot), (R + 8.0, BODY_HW, top_r, bot), (R - 2.0, BODY_HW, top_r, bot)):
        secs.append((x, superellipse(hw, zt, zb, n=48, p=3.4)))
    secs.sort(key=lambda s: s[0])
    body = loft_yz("Stock_body", secs, S, "Polymer")
    auto_sharp(body, 40)
    # --- задняя стойка под затыльник ---
    butt = prism_yz("stock_butt", fillet([(-BUTT_HW, -86.0), (BUTT_HW, -86.0), (BUTT_HW, top_r), (-BUTT_HW, top_r)], [8.0, 8.0, 7.0, 7.0], 6),
                    R - 2.0, R + 14.0, S, "Polymer")
    boolean(body, butt, "UNION")
    # --- нижняя тяга: от низа втулки спереди к носку затыльника ---
    p0, p1 = (F - 16.0, bot + 2.0), (R + 4.0, -80.0)
    dx, dz = p1[0] - p0[0], p1[1] - p0[1]
    ln = math.hypot(dx, dz)
    nx, nz = -dz / ln, dx / ln
    th = 6.8
    strut = prism_xz("stock_strut", [(p0[0] + nx * th, p0[1] + nz * th), (p1[0] + nx * th, p1[1] + nz * th),
                                     (p1[0] - nx * th, p1[1] - nz * th), (p0[0] - nx * th, p0[1] - nz * th)], -11.8, 11.8, S, "Polymer")
    boolean(body, strut, "UNION")
    # тонкая перемычка между втулкой и тягой — бока утоплены (скелет, как на листинге)
    web = prism_xz("stock_web", [(PIN_X0 - 10.0, bot + 1.0), (R + 6.0, bot + 1.0), (R + 6.0, -76.0), (PIN_X0 - 10.0, -44.0)],
                   -2.6, 2.6, S, "Polymer")
    boolean(body, web, "UNION")
    # задний прилив с гнездом QD в перемычке
    qx2, qz2 = R + 28.0, -52.0
    boss = cyl("stock_qd_boss", -11.8, 11.8, 8.2, S, "Polymer", seg=48, cy=qx2, cz=qz2, axis="Y")
    boolean(body, boss, "UNION")
    # --- внутренности: канал трубки, паз направляющей, карман рычага, канал штифта ---
    boolean(body, cyl("cut_stock_bore", R + 2.0, F + 2, TUBE_R + 0.2, S, seg=72))
    boolean(body, box("cut_stock_key", R + 2.0, F + 2, -RIDGE_HALF_W - 0.3, RIDGE_HALF_W + 0.3, RIDGE_Z - 0.4, -8.0, S))
    boolean(body, box("cut_latch_pocket", PIN_X0 - 9.0, LATCH_PIVOT[0] + 5.0, -5.6, 5.6, bot - 2.0, RIDGE_Z - 0.2, S))
    # нижняя тяга спереди — «вилка» вокруг рычага: снизу к нему подходит палец
    boolean(body, box("cut_latch_fork", PIN_X0 - 9.0, LATCH_PIVOT[0] + 5.0, -5.6, 5.6, -70.0, bot - 1.0, S))
    boolean(body, cyl("cut_pin_ch", RIDGE_Z - 3.0, -10.0, 2.6, S, seg=24, cy=PIN_X0, cz=0.0, axis="Z"))
    # гнёзда QD: спереди с обеих сторон втулки и сзади сквозное
    qx1, qz1 = F - 17.0, -14.5
    for s in (-1, 1):
        y0, y1 = (13.15, 25.0) if s > 0 else (-25.0, -13.15)
        boolean(body, cyl(f"cut_qd_front{s}", y0, y1, 6.95, S, seg=48, cy=qx1, cz=qz1, axis="Y"))
        yy0, yy1 = (17.6, 25.0) if s > 0 else (-25.0, -17.6)
        boolean(body, cyl(f"cut_qd_front_cb{s}", yy0, yy1, 7.4, S, seg=48, cy=qx1, cz=qz1, axis="Y"))
    boolean(body, cyl("cut_qd_rear", -20, 20, 6.95, S, seg=48, cy=qx2, cz=qz2, axis="Y"))
    for s in (-1, 1):
        y0, y1 = (10.65, 15.0) if s > 0 else (-15.0, -10.65)
        boolean(body, cyl(f"cut_qd_rear_cb{s}", y0, y1, 7.0, S, seg=48, cy=qx2, cz=qz2, axis="Y"))
    # прорезь антабки в задней стойке (сквозная по Y, для ремня)
    boolean(body, prism_xz("cut_sling_slot", fillet([(R + 3.0, -62.0), (R + 9.0, -62.0), (R + 9.0, -30.0), (R + 3.0, -30.0)], 2.5, 4),
                           -30, 30, S))
    # облегчающий паз сбоку втулки (продольная выемка, как у листинга)
    for s in (-1, 1):
        y0, y1 = (18.55, 25.0) if s > 0 else (-25.0, -18.55)
        boolean(body, prism_xz(f"cut_side_flute{s}", fillet([(F - 40.0, 2.0), (R + 22.0, 3.5), (R + 22.0, 9.5), (F - 40.0, 8.0)], 3.0, 4),
                               y0, y1, S))
    finish(body, w=0.9, seg=3, angle=35)
    lx0, lz0 = R + 50.0, -6.6
    for s in (-1, 1):
        logo_relief(body, LOGO, 5.2, (lx0, side_y(lx0, lz0, s), lz0), s, 0.28, S)
    renormal(body)
    set_origin(body, (F, 0.0, 0.0))
    o["stock_body"] = body
    # --- затыльник: резина, рёбра на задней грани ---
    pad = prism_yz("Stock_buttpad", fillet([(-PAD_HW, -87.0), (PAD_HW, -87.0), (PAD_HW, top_r + 1.0), (-PAD_HW, top_r + 1.0)],
                                           [9.0, 9.0, 8.0, 8.0], 8), R - PAD_T, R - 2.05, S, "Rubber")
    for k in range(int((top_r + 76.0) / 3.6)):
        zz = -78.0 + k * 3.6
        boolean(pad, box("cut_pad_rib", R - PAD_T - 1, R - PAD_T + 1.3, -16.9, 16.9, zz - 0.85, zz + 0.85, S))
    # «носок» и «пятка» скошены
    boolean(pad, prism_xz("cut_pad_toe", [(R - PAD_T - 2, -70.0), (R - PAD_T + 5.0, -92.0), (R - PAD_T - 2, -92.0)], -30, 30, S))
    finish(pad, w=1.2, seg=3, angle=35)
    set_parent(pad, body)
    o["buttpad"] = pad
    # --- гнёзда QD: стальные втулки ---
    cups = []
    for s in (-1, 1):
        y0, y1 = (13.2, 17.85) if s > 0 else (-17.85, -13.2)
        yo = y1 if s > 0 else y0                      # наружный торец
        yi = y0 if s > 0 else y1
        prof = [(yi, QD_R), (yi, 6.9), (yo - 0.2 * s, 6.9), (yo - 0.2 * s, 7.3), (yo, 7.3), (yo, QD_R + 0.5), (yo - 0.5 * s, QD_R)]
        if s < 0:
            prof = [(yo, QD_R + 0.5), (yo, 7.3), (yo + 0.2, 7.3), (yo + 0.2, 6.9), (yi, 6.9), (yi, QD_R), (yo + 0.5, QD_R)]
        c = lathe("qd", prof, S, "Steel_black", seg=48)
        c.rotation_euler = (0, 0, math.pi / 2)
        apply_transform(c)
        c.location = (qx1 * MM, 0, qz1 * MM)
        apply_transform(c)
        c.name = f"Stock_QD_cup_front_{'L' if s > 0 else 'R'}"
        cups.append(c)
    c = lathe("qd", [(-10.8, QD_R + 0.5), (-10.8, 6.9), (10.8, 6.9), (10.8, QD_R + 0.5), (10.3, QD_R), (-10.3, QD_R)],
              S, "Steel_black", seg=48)
    c.rotation_euler = (0, 0, math.pi / 2)
    apply_transform(c)
    c.location = (qx2 * MM, 0, qz2 * MM)
    apply_transform(c)
    c.name = "Stock_QD_cup_rear"
    cups.append(c)
    for c in cups:
        finish(c, w=0.2, seg=2, angle=35)
        set_parent(c, body)
    o["qd_cups"] = cups
    # --- рычаг фиксатора: снизу в кармане, ось спереди (вдоль Y), хвост с рифлением ---
    lx, lz = LATCH_PIVOT
    lev = prism_xz("Stock_latch", fillet([(lx + 3.0, lz + 2.4), (lx + 3.0, lz - 2.4), (PIN_X0 - 7.0, bot - 1.6), (PIN_X0 - 7.5, bot + 1.0),
                                          (PIN_X0 + 4.0, lz + 3.2), (lx - 2.0, lz + 3.2)], [2.4, 2.0, 1.5, 1.5, 1.0, 1.0], 4),
                   -5.0, 5.0, S, "Steel_black")
    for k in range(5):
        xx = PIN_X0 - 5.5 + k * 2.6
        boolean(lev, box("cut_latch_ser", xx - 0.6, xx + 0.6, -6, 6, bot - 3.0, bot - 0.8 + 0.25 * k, S))
    boolean(lev, cyl("cut_latch_axis", -8, 8, 1.25, S, seg=16, cy=lx, cz=lz, axis="Y"))
    finish(lev, w=0.3, seg=2, angle=35)
    set_origin(lev, (lx, 0.0, lz))
    set_parent(lev, body)
    o["latch"] = lev
    o["latch_axis"] = cyl("Stock_latch_axis", -11.0, 11.0, 1.2, S, "Steel_black", seg=16, cy=lx, cz=lz, axis="Y", ch=0.2)
    set_parent(o["latch_axis"], body)
    # штифт фиксатора: вертикальный, верх в отверстии направляющей
    pin = lathe("Stock_lock_pin", [(lz - 1.0, 0.0), (lz - 1.0, 2.25), (RIDGE_Z + 2.6, 2.25), (RIDGE_Z + 3.2, 1.7), (RIDGE_Z + 3.2, 0.0)],
                S, "Steel_black", seg=24)
    pin.rotation_euler = (0, -math.pi / 2, 0)
    apply_transform(pin)
    pin.location = (PIN_X0 * MM, 0, 0)
    apply_transform(pin)
    set_origin(pin, (PIN_X0, 0.0, RIDGE_Z + 3.2))
    set_parent(pin, body)
    o["lock_pin"] = pin
    return o
