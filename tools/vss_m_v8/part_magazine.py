# ВСС-М v8: магазины 9×39 на 10 и 20 патронов — полимерный корпус с «лабиринтными» рёбрами (как у магазинов ВСС-М
# на фото), двухрядная шахматная укладка с подачей поочерёдно из двух рядов, губки по форме патрона, подаватель,
# съёмная крышка с кнопкой, передний зацеп и задний упор под защёлку. Патрон СП-5: гильза 39 мм, длина 56 мм.
# Ось магазина изогнута дугой (низ уходит вперёд); каждый патрон перпендикулярен оси.
import math
import bmesh
import bpy
from mathutils import Matrix, Vector
from lib import (MM, auto_sharp, boolean, fillet, finish, join, lathe, material, set_parent, empty)

P0 = Vector((446.4, -2.6))     # центр верхнего патрона (x, z) в посаженном магазине
THETA0 = math.radians(5.0)     # наклон оси у верха (низ вперёд)
R_CURVE = 420.0                # радиус изгиба оси магазина
D_CART = 11.35                 # диаметр донца гильзы
W_IN = 20.0                    # внутренняя ширина
Y_OFF = (W_IN - D_CART) / 2.0
PITCH = math.sqrt(D_CART ** 2 - (2 * Y_OFF) ** 2)
HALF_N = 30.9                  # половина длины корпуса (вперёд-назад)
HALF_Y = 13.9                  # половина ширины корпуса
U_TOP = 1.9


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


def rrect(hn, hy, r, seg=4):
    return fillet([(-hn, -hy), (hn, -hy), (hn, hy), (-hn, hy)], r, seg)


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


def labyrinth(name, u0, u1, coll, side):
    """Рёбра-лабиринт на боковине: горизонтальные бруски поочерёдно от передней и задней кромки, связки между ними."""
    parts = []
    y_in, y_out = side * (HALF_Y - 0.3), side * (HALF_Y + 1.3)
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
    last_u = (rounds - 1) * PITCH
    u_bot = last_u + D_CART / 2 + 4.0 + 14.0 + (6.0 if rounds > 10 else 0.0)
    steps = max(8, int((u_bot - U_TOP) / 4))
    body = spine_loft(f"Magazine_{tag}", U_TOP, u_bot, steps, rrect(HALF_N, HALF_Y, 3.0), coll, "Polymer_magazine")
    cav = spine_loft("_cav", U_TOP - 3.0, u_bot - 2.4, steps, rrect(HALF_N - 2.4, W_IN / 2, 1.2), coll)
    boolean(body, cav)
    # губки: две полосы над корпусом, внутренняя кромка по форме патрона
    lips = []
    for s in (-1, 1):
        lips.append(spine_box(f"_lip{s}", -4.2, U_TOP + 0.5, -26.5, 23.0, s * 5.2, s * HALF_Y, coll, 2))
    lip = join(lips, "_lips")
    for s in (-1, 1):
        cutp = lathe(f"_lc{s}", [(0, 0), (0, 5.85), (60, 5.85), (60, 0)], coll, None, 40, 0, 0)
        base = to_world(0.0, -28.0, s * Y_OFF)
        cutp.matrix_world = Matrix.Translation(base) @ Vector((1, 0, 0)).rotation_difference(Vector((frame(0)[2].x, 0, frame(0)[2].y))).to_matrix().to_4x4()
        from lib import apply_all
        cutp.data.transform(cutp.matrix_world); cutp.matrix_world = Matrix.Identity(4)
        boolean(lip, cutp)
    boolean(body, lip, op="UNION")
    # передний зацеп и задний упор
    boolean(body, spine_box("_flug", 3.0, 8.0, HALF_N - 0.5, HALF_N + 0.6, -9.0, 9.0, coll, 1), op="UNION")
    boolean(body, spine_box("_rlug", 23.0, 25.9, -HALF_N - 1.6, -HALF_N + 0.5, -6.0, 6.0, coll, 1), op="UNION")
    for s in (-1, 1):
        boolean(body, labyrinth(f"_lab{s}", 14.0, u_bot - 9.0, coll, s), op="UNION", self_x=True)
    finish(body, 1.0, 3, 35)
    # крышка
    plate = spine_loft(f"Magazine_{tag}_floorplate", u_bot - 0.4, u_bot + 3.2, 2, rrect(HALF_N + 1.3, HALF_Y + 1.1, 3.6), coll, "Polymer_magazine")
    btn_c = to_world(u_bot + 3.2, -10.0, 0.0)
    _, d, _, th = frame(u_bot + 3.2)
    btn = lathe(f"Magazine_{tag}_plate_button", [(0, 0), (0, 3.4), (0.6, 3.4), (0.9, 3.0), (0.9, 0)], coll, "Polymer_magazine", 24, 0, 0)
    btn.matrix_world = Matrix.Translation(btn_c) @ Vector((1, 0, 0)).rotation_difference(Vector((d.x, 0, d.y))).to_matrix().to_4x4()
    btn.data.transform(btn.matrix_world); btn.matrix_world = Matrix.Identity(4)
    finish(plate, 1.0, 3, 35)
    auto_sharp(btn, 35)
    # подаватель со ступенькой (уступ — под ряд, из которого подаётся следующий патрон)
    fu = last_u + D_CART / 2 + 0.4
    fol = spine_box(f"Magazine_{tag}_follower", fu, fu + 3.0, -HALF_N + 3.2, HALF_N - 3.2, -W_IN / 2 + 0.4, W_IN / 2 - 0.4, coll, 1)
    step_side = 1 if rounds % 2 == 0 else -1
    boolean(fol, spine_box("_fs", fu - 2.4, fu + 0.4, -HALF_N + 6.0, HALF_N - 6.0, min(0, step_side * 9.6), max(0, step_side * 9.6), coll, 1), op="UNION")
    fol.data.materials.append(material("Polymer_magazine"))
    finish(fol, 0.4, 2, 35)
    # пружина: витая из проволоки прямоугольного контура, витки по оси магазина
    loop = rrect(HALF_N - 5.0, W_IN / 2 - 2.0, 3.5, 3)
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
    # патроны: поочерёдно справа и слева, верхний — справа
    carts = []
    for i in range(rounds):
        u = i * PITCH
        y = -Y_OFF if i % 2 == 0 else Y_OFF
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
    for tag, n in (("10", 10), ("20", 20)):
        sub = collection(f"Magazine_{tag}", C)
        body, plate, btn, fol, spr, carts = build_mag(tag, n, sub, sub, me_cart)
        for o in [plate, btn, fol, spr] + carts:
            set_parent(o, body)
        out[tag] = {"body": body, "plate": plate, "button": btn, "follower": fol, "spring": spr, "rounds": carts}
    return out
