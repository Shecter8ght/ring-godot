# ПП по мотивам KRISS Vector: магазины .45 ACP типа Glock 21 — штатный на 13 (в игре mag_45_vector13) и на 30 с
# удлинителем (mag_45_vector30, как на снимках KRISS и владельца). Корпус — в осях магазина (наклон 21° низом назад,
# part_receiver.mag_frame): сечение — прямоугольник 25.5 × 37.5 со скруглёнными углами (оценка, см. asset-state.md),
# сверху губки, снизу донышко; сзади — контрольные окна с числами (рельефом). Патроны в два ряда в шахматку,
# подаватель. 30-зарядный — в отдельной коллекции Magazine_30 (выключена), ставится на то же место.
import math
import bpy
import bmesh
from mathutils import Matrix, Vector
from lib import (material, MM, MAG_W, MAG_D, BORE_R, lathe, prism_xz, prism_yz, boolean, rounded_prism, fillet, finish_small,
                 set_origin, v)
from part_receiver import mag_frame, MAG_CENTER, rounded_rect_xz

U_TOP = 98.4                   # верх губок вдоль оси от середины горловины: задний угол верха — Z −11.5 (под затвором)
LEN13 = 128.0                  # длина магазина на 13 с донышком (оценка)
LEN30 = 243.0                  # на 30 с удлинителем (снимок KRISS: низ Z −244.6)
WALL = 1.7
CASE_R = 6.0                   # .45 ACP: гильза Ø12.0, длина 22.8, патрон 32.4
CASE_LEN = 22.8
CART_LEN = 32.4
COL_OFF = 4.7                 # смещение рядов от середины
PITCH = 6.78                   # шаг по оси между соседними патронами (шахматка)


def frame_matrix():
    up, fwd = mag_frame()
    c = Vector(MAG_CENTER) * MM
    # локальные оси магазина: x — вперёд (fwd), y — Y, z — вдоль магазина вверх (up)
    return Matrix(((fwd.x, 0, up.x, c.x), (0, 1, 0, c.y), (fwd.z, 0, up.z, c.z), (0, 0, 0, 1)))


def to_frame(o):
    o.data.transform(frame_matrix())


def section(d_half, w_half, rf, rr):
    """Сечение корпуса (вид сверху вдоль оси): x — вперёд, y — поперёк; передние углы rf, задние rr."""
    return fillet([(-d_half, -w_half), (d_half, -w_half), (d_half, w_half), (-d_half, w_half)], [rr, rf, rf, rr], 6)


def shell(name, length, C, mat="Polymer"):
    """Корпус: призма по сечению вдоль оси от низа до верха, внутри — полость, сверху губки (вырез посередине)."""
    d, w = MAG_D / 2, MAG_W / 2
    sec = section(d, w, 5.5, 3.2)
    u0, u1 = U_TOP - length + 5.0, U_TOP
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    a = [bm.verts.new(Vector((x * MM, y * MM, u0 * MM))) for x, y in sec]
    b = [bm.verts.new(Vector((x * MM, y * MM, u1 * MM))) for x, y in sec]
    bm.faces.new(list(reversed(a))); bm.faces.new(b)
    for i in range(len(sec)):
        j = (i + 1) % len(sec)
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me)
    C.objects.link(o)
    o.data.materials.append(material(mat))
    # полость
    inner = section(d - WALL, w - WALL, 4.0, 1.8)
    me2 = bpy.data.meshes.new("_in")
    bm = bmesh.new()
    a = [bm.verts.new(Vector((x * MM, y * MM, (u0 + 3.0) * MM))) for x, y in inner]
    b = [bm.verts.new(Vector((x * MM, y * MM, (u1 + 2.0) * MM))) for x, y in inner]
    bm.faces.new(list(reversed(a))); bm.faces.new(b)
    for i in range(len(inner)):
        j = (i + 1) % len(inner)
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me2); bm.free()
    cut = bpy.data.objects.new("_in", me2)
    C.objects.link(cut)
    boolean(o, cut)
    # губки: вырез по оси сверху (ширина 9 мм) — сзади до 3/4 длины верхнего патрона, загибы — продолжение стенок
    lip = bpy.data.objects.new("_lip", bpy.data.meshes.new("_lip"))
    C.objects.link(lip)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for vv in bm.verts:
        vv.co.x = (-(d - 9.0) if vv.co.x < 0 else d + 2) * MM
        vv.co.y = (-4.6 if vv.co.y < 0 else 4.6) * MM
        vv.co.z = ((u1 - 4.0) if vv.co.z < 0 else u1 + 2) * MM
    bm.to_mesh(lip.data); bm.free()
    boolean(o, lip)
    return o, u0, u1


def witness(o, u1, counts, C):
    """Контрольные окна на задней стенке с числами патронов (окна — круглые, Ø3.2)."""
    for n in counts:
        uc = u1 - CASE_R - 0.6 - (n - 1) * PITCH          # на уровне n-го патрона сверху
        me = bpy.data.meshes.new("_w")
        h = bpy.data.objects.new("_w", me)
        C.objects.link(h)
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=1.6 * MM, radius2=1.6 * MM, depth=8 * MM)
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
        bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((-MAG_D / 2 * MM, 0, uc * MM)))
        bm.to_mesh(me); bm.free()
        boolean(o, h)


def cartridge(name, C):
    """Патрон .45 ACP вдоль +x (пуля вперёд): гильза с проточкой и закраиной, оболочечная пуля с круглым носом."""
    prof = [(0.0, 0.0), (0.0, 6.0), (1.2, 6.0), (1.4, 5.4), (2.2, 5.4), (2.4, 5.95), (CASE_LEN, 6.0), (CASE_LEN, 5.73)]
    case = lathe(name + "_case", [(x - CART_LEN / 2, r) for x, r in prof] + [(CASE_LEN - CART_LEN / 2, 0.0)], C, "Brass",
                 seg=48, cz=0.0)
    nose = []
    for k in range(13):
        a = math.pi / 2 * k / 12
        nose.append((CASE_LEN - 2.0 + (CART_LEN - CASE_LEN + 2.0) * math.sin(a) - CART_LEN / 2, 5.73 * math.cos(a) + 0.0))
    bullet = lathe(name + "_bullet", [(CASE_LEN - 2.0 - CART_LEN / 2, 0.0)] + nose + [(CART_LEN / 2, 0.0)], C,
                   "Bullet_jacket", seg=48, cz=0.0)
    return case, bullet


def rounds(prefix, count, u1, C, coll_name):
    """count патронов: верхний — в губках по середине-ряду, ниже шахматкой; пуля вперёд (по fwd), поперёк оси."""
    objs = []
    base_case, base_bullet = cartridge(prefix + "_proto", C)
    for i in range(count):
        uc = u1 - CASE_R - 0.6 - i * PITCH
        yc = COL_OFF * (1 if i % 2 == 0 else -1)
        for src, nm in ((base_case, "case"), (base_bullet, "bullet")):
            o = bpy.data.objects.new(f"{prefix}_{i:02d}_{nm}", src.data)
            C.objects.link(o)
            o.location = Vector((0.5 * MM, yc * MM, uc * MM))
            o.matrix_world = frame_matrix() @ o.matrix_basis
            objs.append(o)
    for o in (base_case, base_bullet):
        bpy.data.objects.remove(o, do_unlink=True)
    return objs


def magazine(name, length, count, counts, C):
    o, u0, u1 = shell(name + "_body", length, C)
    witness(o, u1, counts, C)
    finish_small(o, w=0.4, seg=3)
    # донышко: пластина с выступом-«пяткой» спереди
    d, w = MAG_D / 2, MAG_W / 2
    bp = bpy.data.objects.new(name + "_floorplate", bpy.data.meshes.new(name + "_floorplate"))
    C.objects.link(bp)
    bm = bmesh.new()
    sec = section(d + 1.2, w + 1.0, 6.5, 4.0)
    a = [bm.verts.new(Vector((x * MM, y * MM, (u0 - 4.0) * MM))) for x, y in sec]
    b = [bm.verts.new(Vector((x * MM, y * MM, (u0 + 2.0) * MM))) for x, y in sec]
    bm.faces.new(list(reversed(a))); bm.faces.new(b)
    for i in range(len(sec)):
        j = (i + 1) % len(sec)
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(bp.data); bm.free()
    bp.data.materials.append(material("Polymer"))
    finish_small(bp, w=0.5, seg=3)
    # подаватель — под нижним патроном
    fu = u1 - CASE_R - 0.6 - (count - 1) * PITCH - CASE_R - 1.5
    fl = bpy.data.objects.new(name + "_follower", bpy.data.meshes.new(name + "_follower"))
    C.objects.link(fl)
    bm = bmesh.new()
    sec = section(d - WALL - 0.3, w - WALL - 0.3, 3.5, 1.5)
    a = [bm.verts.new(Vector((x * MM, y * MM, (fu - 6.0) * MM))) for x, y in sec]
    b = [bm.verts.new(Vector((x * MM, y * MM, fu * MM))) for x, y in sec]
    bm.faces.new(list(reversed(a))); bm.faces.new(b)
    for i in range(len(sec)):
        j = (i + 1) % len(sec)
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(fl.data); bm.free()
    fl.data.materials.append(material("Polymer"))
    finish_small(fl, w=0.4, seg=3)
    for x in (o, bp, fl):
        to_frame(x)
    bp["owner"] = o.name
    fl["owner"] = o.name
    rs = rounds(name + "_round", count, u1, C, C.name)
    for r in rs:
        r.parent = None
    o["mag_capacity"] = count
    return o, bp, fl, rs


def build(ctx):
    C = ctx["coll"]["Magazine"]
    m13 = magazine("Magazine13", LEN13, 13, (6, 9, 13), C)
    C30 = bpy.data.collections.get("Magazine_30") or bpy.data.collections.new("Magazine_30")
    if C30.name not in [c.name for c in ctx["coll"]["Magazine"].children]:
        ctx["coll"]["Magazine"].children.link(C30)
    m30 = magazine("Magazine30", LEN30, 30, (10, 20, 30), C30)
    sleeve(m30[0], LEN30, C30)
    return {"mag13": m13, "mag30": m30, "coll30": C30}


def sleeve(body, length, C):
    """Удлинитель 30-зарядного (снимки KRISS A/B, владельца 01/04): рукав поверх нижней части корпуса — толще на 0.9
    с каждой стороны, сверху уступ со скосом, спереди — поперечные рёбра (канавки шагом 3.6 по плоской части передней
    грани), сзади — гладкий."""
    d, w = MAG_D / 2 + 0.9, MAG_W / 2 + 0.9
    u_top = U_TOP - length + 5.0 + 128.0          # верх рукава — там, где кончился бы штатный на 13
    u_bot = U_TOP - length + 5.0
    sec = section(d, w, 6.0, 3.6)
    me = bpy.data.meshes.new("Magazine30_sleeve")
    bm = bmesh.new()
    rings = []
    for uu, k in ((u_bot, 0.0), (u_top - 2.0, 0.0), (u_top, 0.9)):
        rings.append([bm.verts.new(Vector(((x - math.copysign(k, x)) * MM, (y - math.copysign(k, y)) * MM, uu * MM)))
                      for x, y in sec])
    bm.faces.new(list(reversed(rings[0]))); bm.faces.new(rings[-1])
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(len(sec)):
            j = (i + 1) % len(sec)
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new("Magazine30_sleeve", me)
    C.objects.link(o)
    o.data.materials.append(material("Polymer"))
    # внутри — по корпусу магазина (рукав надет на него)
    inn = section(MAG_D / 2 - 0.02, MAG_W / 2 - 0.02, 5.5, 3.2)
    me2 = bpy.data.meshes.new("_sin")
    bm = bmesh.new()
    a = [bm.verts.new(Vector((x * MM, y * MM, (u_bot - 5.0) * MM))) for x, y in inn]
    b = [bm.verts.new(Vector((x * MM, y * MM, (u_top + 5.0) * MM))) for x, y in inn]
    bm.faces.new(list(reversed(a))); bm.faces.new(b)
    for i in range(len(inn)):
        j = (i + 1) % len(inn)
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me2); bm.free()
    ci = bpy.data.objects.new("_sin", me2)
    C.objects.link(ci)
    boolean(o, ci)
    # рёбра спереди: канавки поперёк передней грани (в осях магазина — по x = +d), ширина 1.5, глубина 0.8
    n = int((u_top - u_bot - 12.0) / 3.6)
    for i in range(n):
        uc = u_bot + 8.0 + i * 3.6
        g = bpy.data.objects.new("_sg", bpy.data.meshes.new("_sg"))
        C.objects.link(g)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for vv in bm.verts:
            vv.co.x = ((d - 0.8) if vv.co.x < 0 else d + 2.0) * MM
            vv.co.y = ((-w + 4.2) if vv.co.y < 0 else (w - 4.2)) * MM
            vv.co.z = ((uc - 0.75) if vv.co.z < 0 else (uc + 0.75)) * MM
        bm.to_mesh(g.data); bm.free()
        boolean(o, g)
    finish_small(o, w=0.4, seg=3)
    to_frame(o)
    o["owner"] = body.name
    return o
