# ВСС-М v8: магазины 9×39 на 10, 20 и 30 патронов — полиамидный корпус с рёбрами, двухрядная шахматная укладка
# с однорядным выходом (журнал «Братишка» 2000/2): у горловины ряды сходятся к середине, верхний патрон — по центру
# под обеими губками. Габарит по магазинам ТОЗ: 70×33×108 (10), 70×33×160 (20). Патрон СП-5: длина 56, донце 11.35;
# гильза почти без конусности, поэтому магазин почти прямой. Каждый патрон перпендикулярен оси магазина.
import math
import bmesh
import bpy
from mathutils import Matrix, Vector
from lib import (MM, auto_sharp, boolean, fillet, finish, join, lathe, material, set_parent, empty)

P0 = Vector((446.4, -2.6))     # центр верхнего патрона (x, z) в посаженном магазине
THETA0 = math.radians(5.0)     # наклон оси у верха (низ вперёд)
R_CURVE = 1300.0               # радиус изгиба оси магазина (почти прямой)
D_CART = 11.35                 # диаметр донца гильзы
W_IN = 21.45                   # внутренняя ширина в двухрядной части: шаг 5.18 мм на патрон, как у магазинов ТОЗ
Y_OFF = (W_IN - D_CART) / 2.0
PITCH = math.sqrt(D_CART ** 2 - (2 * Y_OFF) ** 2)
HALF_N = 33.0                  # задняя полудлина корпуса (вперёд-назад от оси патрона)
HALF_NF = 31.6                 # передняя полудлина (передняя стенка у патронника)
HALF_Y = 15.25                 # половина ширины корпуса (с рёбрами ~33 мм)
U_TOP = 1.9
SPRING_SPACE = 34.0            # сжатая пружина и ход подавателя (по высоте магазинов ТОЗ)
NECK_W = D_CART / 2 + 0.2      # полуширина горловины у верхнего патрона


def round_positions(n):
    """(u, y) центров патронов сверху вниз: верхний по центру, второй смещён, дальше — шахматные ряды."""
    pos = [(0.0, 0.0)]
    if n > 1:
        y1 = 2.6
        pos.append((math.sqrt(D_CART ** 2 - y1 ** 2), y1))
    if n > 2:
        dy = Y_OFF + 2.6
        pos.append((pos[1][0] + math.sqrt(D_CART ** 2 - dy ** 2), -Y_OFF))
    k = 3
    while len(pos) < n:
        pos.append((pos[-1][0] + PITCH, Y_OFF if k % 2 == 1 else -Y_OFF))
        k += 1
    return pos


def inner_half_width(u):
    """Внутренняя полуширина вдоль оси: горловина у верха, расширение к двухрядной части."""
    a, b, c = 1.0, 11.0, 17.0
    w_b = 2.6 + D_CART / 2 + 0.15
    if u <= a:
        return NECK_W
    if u <= b:
        return NECK_W + (w_b - NECK_W) * (u - a) / (b - a)
    if u <= c:
        t = (u - b) / (c - b)
        return w_b + (W_IN / 2 - w_b) * (t * t * (3 - 2 * t))
    return W_IN / 2


def frame(u):
    """Точка оси (x, z), направление вниз по оси d и перпендикуляр вперёд f — в плоскости XZ."""
    steps = max(1, int(abs(u) / 0.5))
    p = Vector(P0)
    du = u / steps
    for k in range(steps):
        th = THETA0 + (k + 0.5) * du / R_CURVE
        p += Vector((math.sin(th), -math.cos(th))) * du
    th = THETA0 + u / R_CURVE
    d = Vector((math.sin(th), -math.cos(th)))
    f = Vector((math.cos(th), math.sin(th)))
    return p, d, f, th


def to_world(u, n, y):
    p, d, f, th = frame(u)
    q = p + f * n
    return Vector((q.x * MM, y * MM, q.y * MM))


def spine_loft(name, u0, u1, n_steps, sec, coll, mat=None, cap=True):
    """Лофт сечения sec=[(n, y)…] вдоль изогнутой оси от u0 до u1."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = []
    for i in range(n_steps + 1):
        u = u0 + (u1 - u0) * i / n_steps
        rings.append([bm.verts.new(to_world(u, n, y)) for n, y in sec])
    m = len(sec)
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(m):
            j = (i + 1) % m
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    if cap:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    if mat:
        me.materials.append(material(mat))
    return o


def spine_box(name, u0, u1, n0, n1, y0, y1, coll, steps=1):
    sec = [(n0, y0), (n1, y0), (n1, y1), (n0, y1)]
    return spine_loft(name, u0, u1, steps, sec, coll)


def rrect(hn, hy, r, seg=4, hnf=None):
    hnf = hn if hnf is None else hnf
    return fillet([(-hn, -hy), (hnf, -hy), (hnf, hy), (-hn, hy)], r, seg)


def funnel_loft(name, u0, u1, coll):
    """Полость магазина: сечение сужается к горловине (однорядный выход)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    # сечения через 4 мм до низа: ось изогнута (R1300), прямой отрезок полости на длинном магазине выходил хордой
    # сквозь переднюю стенку (на 30-м — окно ~3 мм, замечание владельца 25.10)
    us = [u0, -1.0, 1.0] + [1.0 + k * 1.0 for k in range(1, 18)] + [float(u) for u in range(22, int(u1), 4)] + [u1]
    rings = []
    for u in us:
        w = inner_half_width(max(u, 0.0))
        sec = rrect(HALF_N - 2.4, w, 1.2, 4, HALF_NF - 2.4)
        rings.append([bm.verts.new(to_world(u, n, y)) for n, y in sec])
    m = len(rings[0])
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(m):
            j = (i + 1) % m
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    return o


def cartridge_mesh():
    """Патрон СП-5 вдоль +X, донце в x=0."""
    me = bpy.data.meshes.get("Cartridge_SP5_mesh")
    if me is not None:
        return me
    coll = bpy.context.scene.collection
    case = lathe("_case", [(0.0, 2.6), (0.0, 5.45), (0.25, 5.67), (1.25, 5.67), (1.45, 5.2), (1.75, 4.75), (2.6, 4.75),
                           (2.95, 5.6), (3.2, 5.64), (31.4, 5.22), (33.0, 5.03), (38.6, 5.03), (38.95, 4.75),
                           (38.95, 4.25), (0.6, 4.25), (0.6, 2.6)], coll, None, 40, 0, 0)
    primer = lathe("_primer", [(0.15, 0.0), (0.15, 2.55), (0.35, 2.62), (0.9, 2.62), (0.9, 0.0)], coll, None, 24, 0, 0)
    bullet = lathe("_bullet", [(30.0, 0.0), (30.0, 4.4), (31.0, 4.62), (44.0, 4.62), (47.5, 4.42), (51.0, 3.78), (54.0, 2.7),
                               (55.5, 1.75), (56.0, 1.2), (56.0, 0.0)], coll, None, 40, 0, 0)
    for o, mname in ((case, "Case_steel_lacquer"), (primer, "Bullet_jacket"), (bullet, "Bullet_jacket")):
        o.data.materials.append(material(mname))
        auto_sharp(o, 32)
    o = join([case, primer, bullet], "_cart")
    me = o.data
    me.name = "Cartridge_SP5_mesh"
    bpy.data.objects.remove(o, do_unlink=True)
    return me


def cartridge(name, base_world, axis_world, coll, me=None):
    me = me or cartridge_mesh()
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    ax = Vector(axis_world).normalized()
    rot = Vector((1, 0, 0)).rotation_difference(ax).to_matrix().to_4x4()
    o.matrix_world = Matrix.Translation(base_world) @ rot
    return o


LIP_T = 1.8          # толщина губки
LIP_GAP = 4.2        # половина просвета между губками над верхним патроном (сзади)
LIP_FRONT = 3.0      # губки кончаются чуть впереди середины гильзы; дальше — окно выхода патрона


def _lip_section(side, y_edge, steps=10):
    """Сечение губки (y, h): h — высота над осью верхнего патрона вдоль оси магазина. Губка — продолжение стенки,
    загнута внутрь над патроном своего ряда; нижняя поверхность повторяет патрон с зазором 0.15 мм."""
    yc = 0.0                                                       # однорядный выход: верхний патрон по центру
    ri = D_CART / 2 + 0.15
    ro = ri + LIP_T
    # угол кромки на окружности ri (от оси +y, против часовой) — где y = y_edge
    ce = max(-1.0, min(1.0, (y_edge - yc) / ri))
    a_edge = math.degrees(math.acos(ce))
    a_wall = 180.0 if side < 0 else 0.0
    pts = []
    pts.append((side * NECK_W, -4.5))                             # низ внутренней стенки (уходит в корпус)
    for k in range(steps + 1):                                     # внутренняя дуга: от стенки к кромке
        a = math.radians(a_wall + (a_edge - a_wall) * k / steps)
        pts.append((yc + ri * math.cos(a), ri * math.sin(a)))
    for k in range(steps + 1):                                     # наружная дуга: от кромки обратно к стенке
        a = math.radians(a_edge + (a_wall - a_edge) * k / steps * 0.72)
        pts.append((yc + ro * math.cos(a), ro * math.sin(a)))
    pts.append((side * HALF_Y, 1.5))
    pts.append((side * HALF_Y, -4.5))
    if side > 0:
        pts.reverse()
    return pts


def lips(name, coll):
    """Обе губки: сечение протянуто вдоль n от задней стенки до LIP_FRONT; спереди кромка расходится наружу."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    for side in (-1, 1):
        ns = [-HALF_N + 0.2 + k * 1.6 for k in range(int((LIP_FRONT + HALF_N - 0.2) / 1.6) + 1)]
        rings = []
        for n in ns:
            t = max(0.0, min(1.0, (n + 9.0) / (LIP_FRONT + 9.0)))
            y_edge = side * (LIP_GAP + 3.4 * t * t)                # к выходу губки расходятся
            sec = _lip_section(side, y_edge)
            rings.append([bm.verts.new(to_world(-h, n, y)) for y, h in sec])
        m = len(rings[0])
        for r0, r1 in zip(rings, rings[1:]):
            for i in range(m):
                j = (i + 1) % m
                bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    return o


def labyrinth(name, u0, u1, coll, side):
    """Рёбра-лабиринт на боковине: горизонтальные бруски поочерёдно от передней и задней кромки, связки между ними."""
    parts = []
    y_in, y_out = side * (HALF_Y - 0.3), side * (HALF_Y + 0.9)
    y0, y1 = min(y_in, y_out), max(y_in, y_out)
    k = 0
    u = u0
    step = 8.6
    while u + step < u1:
        if k % 2 == 0:
            parts.append(spine_box(f"_lb{k}", u, u + 2.4, -24.0, 13.0, y0, y1, coll, 1))
        else:
            parts.append(spine_box(f"_lb{k}", u, u + 2.4, -13.0, 24.0, y0, y1, coll, 1))
        if u + step + 1.8 < u1:
            nlink = 11.2 if k % 2 == 0 else -11.2
            parts.append(spine_box(f"_ll{k}", u + 1.2, u + step + 1.2, nlink - 1.2, nlink + 1.2, y0, y1, coll, 2))
        u += step
        k += 1
    o = join(parts, name)
    return o


def build_mag(tag, rounds, coll, cart_coll, me_cart):
    rpos = round_positions(rounds)
    last_u = rpos[-1][0]
    u_bot = last_u + D_CART / 2 + 3.0 + SPRING_SPACE
    steps = max(8, int((u_bot - U_TOP) / 4))
    body = spine_loft(f"Magazine_{tag}", U_TOP, u_bot, steps, rrect(HALF_N, HALF_Y, 3.0, 4, HALF_NF), coll, "Polymer_magazine")
    cav = funnel_loft("_cav", U_TOP - 3.0, u_bot - 2.4, coll)
    boolean(body, cav)
    # губки: загнуты над патронами своих рядов; задняя стенка над губками закрыта
    boolean(body, lips("_lips", coll), op="UNION", self_x=True)
    boolean(body, spine_box("_rwall", -3.0, U_TOP + 1.0, -HALF_N, -HALF_N + 2.4, -HALF_Y, HALF_Y, coll, 1), op="UNION")
    # передний зацеп и задний упор
    boolean(body, spine_box("_flug", 3.0, 8.0, HALF_NF - 0.5, HALF_NF + 0.6, -9.0, 9.0, coll, 1), op="UNION")
    boolean(body, spine_box("_rlug", 23.0, 25.9, -HALF_N - 1.6, -HALF_N + 0.5, -6.0, 6.0, coll, 1), op="UNION")
    for s in (-1, 1):
        boolean(body, labyrinth(f"_lab{s}", 14.0, u_bot - 9.0, coll, s), op="UNION", self_x=True)
    finish(body, 1.0, 3, 35)
    # крышка
    plate = spine_loft(f"Magazine_{tag}_floorplate", u_bot - 0.4, u_bot + 3.2, 2, rrect(HALF_N + 1.3, HALF_Y + 1.1, 3.6, 4, HALF_NF + 1.3), coll, "Polymer_magazine")
    btn_c = to_world(u_bot + 3.2, -10.0, 0.0)
    _, d, _, th = frame(u_bot + 3.2)
    btn = lathe(f"Magazine_{tag}_plate_button", [(0, 0), (0, 3.4), (0.6, 3.4), (0.9, 3.0), (0.9, 0)], coll, "Polymer_magazine", 24, 0, 0)
    btn.matrix_world = Matrix.Translation(btn_c) @ Vector((1, 0, 0)).rotation_difference(Vector((d.x, 0, d.y))).to_matrix().to_4x4()
    btn.data.transform(btn.matrix_world); btn.matrix_world = Matrix.Identity(4)
    finish(plate, 1.0, 3, 35)
    auto_sharp(btn, 35)
    # подаватель со ступенькой (уступ — под ряд, из которого подаётся следующий патрон)
    fu = last_u + D_CART / 2 + 0.4
    fol = spine_box(f"Magazine_{tag}_follower", fu, fu + 3.0, -HALF_N + 3.2, HALF_NF - 3.2, -W_IN / 2 + 0.4, W_IN / 2 - 0.4, coll, 1)
    fol.data.materials.append(material("Polymer_magazine"))
    step_side = 1 if rpos[-1][1] < 0 else -1                     # ступенька под ряд, противоположный последнему патрону
    boolean(fol, spine_box("_fs", fu - 2.4, fu + 0.4, -HALF_N + 6.0, HALF_NF - 6.0, min(0, step_side * 10.2), max(0, step_side * 10.2), coll, 1), op="UNION")
    finish(fol, 0.4, 2, 35)
    # пружина: витая из проволоки прямоугольного контура, витки по оси магазина
    loop = rrect(HALF_N - 5.0, W_IN / 2 - 2.0, 3.5, 3, HALF_NF - 5.0)
    turns = max(3, int((u_bot - fu - 6.0) // 6.5))
    pts = []
    for t_ in range(turns):
        for k_, (n_, y_) in enumerate(loop):
            u_ = fu + 3.6 + (t_ + k_ / len(loop)) * (u_bot - 3.0 - fu - 3.6) / turns
            pts.append(to_world(u_, n_, y_))
    cu = bpy.data.curves.new(f"Magazine_{tag}_spring", "CURVE"); cu.dimensions = "3D"
    sp_ = cu.splines.new("POLY"); sp_.points.add(len(pts) - 1)
    for k_, p_ in enumerate(pts):
        sp_.points[k_].co = (p_.x, p_.y, p_.z, 1.0)
    cu.bevel_depth = 0.55 * MM; cu.bevel_resolution = 1
    so = bpy.data.objects.new("_spc", cu); coll.objects.link(so)
    dg = bpy.context.evaluated_depsgraph_get()
    me_s = bpy.data.meshes.new_from_object(so.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(so, do_unlink=True); bpy.data.curves.remove(cu)
    spr = bpy.data.objects.new(f"Magazine_{tag}_spring", me_s); coll.objects.link(spr)
    me_s.materials.append(material("Spring_steel"))
    for p_ in me_s.polygons:
        p_.use_smooth = True
    # патроны: верхний по центру под губками, ниже — шахматные ряды
    carts = []
    for i, (u, y) in enumerate(rpos):
        p, d, f, th = frame(u)
        base = to_world(u, -28.0, y)
        ax = Vector((f.x, 0, f.y))
        carts.append(cartridge(f"Magazine_{tag}_round_{i + 1:02d}", base, ax, cart_coll, me_cart))
    return body, plate, btn, fol, spr, carts


def build(ctx):
    C = ctx["coll"]["Magazines"]
    from lib import collection
    me_cart = cartridge_mesh()
    out = {}
    for tag, n in (("10", 10), ("20", 20), ("30", 30)):
        sub = collection(f"Magazine_{tag}", C)
        body, plate, btn, fol, spr, carts = build_mag(tag, n, sub, sub, me_cart)
        for o in [plate, btn, fol, spr] + carts:
            set_parent(o, body)
        out[tag] = {"body": body, "plate": plate, "button": btn, "follower": fol, "spring": spr, "rounds": carts}
    return out
