"""«Проспект», дом 7 — материалы v01 поверх принятой формы (форму-файл не трогает: открывает его и сохраняет рядом).
  blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_houses/house7_finish.py -- <выход.blend> \
      [preview <папка>] [only cam,cam] [res 1400x875] [samples 64]
Материалы — materials.py (плиточные фото-наборы CC0 в мировых координатах + фото-маски владельца), здесь: подстановка материалов
в слоты, особые материалы отдельных объектов, декали потёков, растения клумбы, мир (пасмурное HDRI), камеры и кадры Cycles."""
import math
import os
import random
import zlib
import sys

import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import materials as MT

LIB = "E:/Models Blender/ENVIRONMENT/RING_Prospekt_Houses"
FORM = LIB + "/models/RING_Prospekt_House7_v01.blend"
HDRI = "E:/Games/RING-godot/assets/sky/kloofendal_overcast_puresky.hdr"
PLANTS = "E:/Models Blender/ENVIRONMENT/RING_Prospekt_Plants/models/04_Сирень_PBR_v01.blend"
HY = 13.0
H_ROOF = 37.5

OVER = {
    "H7_ServiceDoor": {"dark_panel": "door_steel"},
    "H7_PortalGlazing": {"panel_beige": "plaster_light", "wood": "floor_tile", "glass": "glass_dark"},
    "preview_ground": {"preview_ground": "asphalt_wet"},
    "courtyard_tile": {"concrete": "apron"},
    "H7_Vestibule": {"concrete": "floor_tile", "panel_beige": "plaster_light"},
    "preview_police": {"concrete": "preview_police"},
}


def fold_panel(bm, xa, xb, z0, z1, y, mi, folds, amp, seed):
    """Полотно шторы со складками: сетка, смещение по y — сумма неравных синусов (мягкие неравные складки), к низу чуть сильнее."""
    if xb - xa < 0.04:
        return
    rng = random.Random(seed)
    ph, ph2 = rng.uniform(0, 6.28), rng.uniform(0, 6.28)
    nc = max(8, int((xb - xa) / 0.02))
    nr = 12
    vs = {}
    for i in range(nc + 1):
        u = i / nc
        base = amp * (0.55 * math.sin(2 * math.pi * folds * u + ph) + 0.30 * math.sin(2 * math.pi * folds * 2.3 * u + ph2)
                      + 0.15 * math.sin(2 * math.pi * folds * 0.55 * u + ph))
        for j in range(nr + 1):
            t = j / nr
            yy = y + base * (0.6 + 0.4 * (1 - t)) + 0.012 * math.sin(3.1 * t + ph) * (1 - u)
            xx = xa + (xb - xa) * u + 0.012 * math.sin(2 * math.pi * folds * u) * (1 - t)
            vs[(i, j)] = bm.verts.new((xx, yy, z0 + (z1 - z0) * t))
    for i in range(nc):
        for j in range(nr):
            f = bm.faces.new((vs[(i, j)], vs[(i + 1, j)], vs[(i + 1, j + 1)], vs[(i, j + 1)]))
            f.material_index = mi
            f.smooth = True


def rebuild_curtains():
    """Заглушки-полоски заменяются шторами со складками (кроме варианта b у окон — вертикальные жалюзи, ~четверть окон)."""
    n = 0
    for col in bpy.data.collections["Модули"].children:
        nm = col.name
        if not (nm.startswith("H_Window") or nm.startswith("H_Loggia")):
            continue
        parts = nm.split("_")
        var = parts[-2] if len(parts) >= 3 and len(parts[-2]) == 1 and parts[-2] in "abcd" else None
        if not var or (nm.startswith("H_Window") and var == "b"):
            continue
        ob = col.objects[0]
        me = ob.data
        names = [mm.name.split(".")[0] if mm else "" for mm in me.materials]
        ci = [i for i, x in enumerate(names) if x == "штора_заглушка"]
        ti = [i for i, x in enumerate(names) if x == "тюль_заглушка"]
        idx = set(ci + ti)
        bm = bmesh.new()
        bm.from_mesh(me)
        faces = [f for f in bm.faces if f.material_index in idx]
        if not faces:
            bm.free()
            continue
        xs = [v.co.x for f in faces for v in f.verts]
        zs = [v.co.z for f in faces for v in f.verts]
        ys = [v.co.y for f in faces for v in f.verts]
        xa, xb, z0, z1, y = min(xs), max(xs), min(zs), max(zs), min(ys)
        bmesh.ops.delete(bm, geom=faces, context="FACES")
        loggia = nm.startswith("H_Loggia")
        mi = ci[0] if ci else 0
        amp = 0.02 if loggia else 0.035
        yb = 1.255 if loggia else y - 0.02
        mid = (xa + xb) / 2
        seed = zlib.crc32(nm.encode())
        if var == "d" and ti:
            fold_panel(bm, xa, xb, z0, z1, y, ti[0], max(6, int((xb - xa) / 0.11)), 0.012, seed)
        elif var in ("a",) and not loggia:
            fold_panel(bm, xa, mid - 0.005, z0, z1, yb, mi, max(4, int((mid - xa) / 0.13)), amp, seed)
            fold_panel(bm, mid + 0.005, xb, z0, z1, yb, mi, max(4, int((xb - mid) / 0.13)), amp, seed + 1)
        elif loggia and var == "a":
            fold_panel(bm, xa, mid - 0.005, z0, z1, yb, mi, max(4, int((mid - xa) / 0.13)), amp, seed)
            fold_panel(bm, mid + 0.005, xb, z0, z1, yb, mi, max(4, int((xb - mid) / 0.13)), amp, seed + 1)
        else:                                  # собраны по краям (окна c, лоджии b и c)
            wd = 0.32 if var == "c" else 0.4
            fold_panel(bm, xa, xa + wd, z0, z1, yb, mi, 5, amp * 1.2, seed)
            fold_panel(bm, xb - wd, xb, z0, z1, yb, mi, 5, amp * 1.2, seed + 1)
        bm.to_mesh(me)
        bm.free()
        n += 1
    print("curtains rebuilt", n)


def vestibule():
    """Вестибюль с глубиной: в ядре дома вырезана полость 5,9 × 4,0 × 3,3 м за витражом, внутри плитка, штукатурка, лифты,
    почтовые ящики, ряды потолочных светильников, скамья. Старую заднюю стенку формы убираем (форма-файл не меняется)."""
    import kit
    ob = bpy.data.collections["H7_PortalGlazing"].objects[0]
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    names = [m.name if m else "" for m in ob.data.materials]
    kill = {i for i, n in enumerate(names) if n.split(".")[0] in ("panel_beige", "wood", "lamp")}
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index in kill], context="FACES")
    bm.to_mesh(ob.data)
    bm.free()
    X0, X1, Y0, Y1, Z0, Z1 = -3.95, 1.95, -11.4, -7.4, 0.15, 3.45
    core = bpy.data.collections["H7_Core"].objects[0]
    b = kit.B("H7_Core_new")
    b.box(-16.4, X0, -11.4, 11.4, 0.0, 37.5, "concrete")
    b.box(X1, 16.4, -11.4, 11.4, 0.0, 37.5, "concrete")
    b.box(X0, X1, Y1, 11.4, 0.0, 37.5, "concrete")
    b.box(X0, X1, Y0, Y1, 0.0, Z0, "concrete")
    b.box(X0, X1, Y0, Y1, Z1, 37.5, "concrete")
    nb = b.build()
    old = core.data
    core.data = nb.data
    bpy.data.meshes.remove(old)
    core.data.materials.clear()
    core.data.materials.append(kit.get_mat("concrete"))
    v = kit.B("H7_Vestibule")
    ya = -12.4
    v.box(X0, X1, ya, Y1, Z0, Z0 + 0.02, "concrete")                                  # пол — плитка
    v.box(X0, X0 + 0.02, ya, Y1, Z0 + 0.02, Z1, "panel_beige")                        # стены — светлая штукатурка
    v.box(X1 - 0.02, X1, ya, Y1, Z0 + 0.02, Z1, "panel_beige")
    v.box(X0, X1, Y1 - 0.02, Y1, Z0 + 0.02, Z1, "panel_beige")
    v.box(X0, X1, ya, Y1, Z1 - 0.03, Z1, "panel_beige")                               # потолок
    for i in range(3):                                                                 # две створки лифта ×2 с рамой
        xl = -2.9 + i * 1.5
        v.box(xl - 0.06, xl + 1.02, Y1 - 0.07, Y1 - 0.02, Z0 + 0.02, Z0 + 2.2, "alu_frame", bev=0.004)
        v.box(xl, xl + 0.48, Y1 - 0.06, Y1 - 0.03, Z0 + 0.03, Z0 + 2.15, "steel", bev=0.003)
        v.box(xl + 0.5, xl + 0.96, Y1 - 0.06, Y1 - 0.03, Z0 + 0.03, Z0 + 2.15, "steel", bev=0.003)
    for r in range(3):                                                                 # почтовые ящики на правой стене: 3 × 8
        for c in range(8):
            yy = -10.7 + c * 0.30
            zz = 1.0 + r * 0.26
            v.box(X1 - 0.08, X1 - 0.02, yy, yy + 0.27, zz, zz + 0.23, "steel", bev=0.003)
            v.box(X1 - 0.085, X1 - 0.075, yy + 0.05, yy + 0.22, zz + 0.15, zz + 0.17, "interior")
    for j in range(3):                                                                 # потолочные светильники рядами 3 × 3
        for i in range(3):
            v.box(-3.3 + i * 1.9, -2.2 + i * 1.9, Y0 + 0.4 + j * 1.2, Y0 + 0.65 + j * 1.2, Z1 - 0.05, Z1 - 0.03, "lamp")
    v.box(X0 + 0.02, X0 + 0.52, -10.2, -8.6, Z0 + 0.02 + 0.40, Z0 + 0.02 + 0.44, "wood", bev=0.005)     # скамья
    for yy in (-10.15, -8.65):
        v.box(X0 + 0.04, X0 + 0.50, yy, yy + 0.04, Z0 + 0.02, Z0 + 0.02 + 0.40, "steel")
    obj = v.build()
    asm = bpy.data.collections["Дом7_сборка"]
    asm.objects.link(obj)
    # отмостка вокруг дома: бетон с неровным краем, трещинами; толщина 5 см
    import random as _r
    rr = _r.Random(3)
    cb = bmesh.new()
    for (x0, x1, y0, y1) in ((-30.0, 30.0, -24.0, -13.0), (-30.0, 30.0, 13.0, 24.0), (-30.0, -18.0, -13.0, 13.0), (18.0, 30.0, -13.0, 13.0)):
        nx, ny = int(round(x1 - x0)), int(round(y1 - y0))
        grid = {}
        for i in range(nx + 1):
            for j in range(ny + 1):
                x = x0 + (x1 - x0) * i / nx
                y = y0 + (y1 - y0) * j / ny
                if i == 0 or i == nx or j == 0 or j == ny:                       # неровный наружный край ±0,3 м (шов у стены — ровный)
                    near_wall = abs(abs(y) - 13.0) < 0.01 and y0 != -13.0 or abs(abs(x) - 18.0) < 0.01
                    if not near_wall:
                        x += rr.uniform(-0.3, 0.3)
                        y += rr.uniform(-0.3, 0.3)
                grid[(i, j)] = cb.verts.new((x, y, 0.010 + rr.uniform(-0.004, 0.004)))
        for i in range(nx):
            for j in range(ny):
                f = cb.faces.new((grid[(i, j)], grid[(i + 1, j)], grid[(i + 1, j + 1)], grid[(i, j + 1)]))
                f.material_index = 0
    ext = bmesh.ops.extrude_face_region(cb, geom=list(cb.faces))
    for v in [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]:
        v.co.z -= 0.05
    bmesh.ops.recalc_face_normals(cb, faces=cb.faces)
    me = bpy.data.meshes.new("courtyard_tile")
    cb.to_mesh(me)
    cb.free()
    me.materials.append(kit.get_mat("concrete"))
    cob = bpy.data.objects.new("courtyard_tile", me)
    asm.objects.link(cob)


def rebuild_beds():
    """Клумба: стенки без щелей-дыр, дренажные отверстия — тёмные прорези на лицевой стороне (форма-файл не меняется)."""
    import kit
    col = bpy.data.collections["H7_PortalBeds"]
    ob = col.objects[0]
    kit.set_root(bpy.data.collections["Модули"])
    b = kit.B("H7_PortalBeds_new")
    X0, X1, wt = 2.3, 5.7, 0.14
    for (h, ya, yb) in ((1.35, -HY, -HY - 0.7), (0.90, -HY - 0.7, -HY - 1.4), (0.45, -HY - 1.4, -HY - 2.1)):
        b.box(X0 + wt, X1 - wt, yb + wt, ya, 0.0, h - 0.30, "concrete")
        b.box(X0, X0 + wt, yb, ya, 0.0, h, "concrete")
        b.box(X1 - wt, X1, yb, ya, 0.0, h, "concrete")
        b.box(X0 + wt, X1 - wt, yb, yb + wt, 0.0, h, "concrete")
        for xs in (X0 + 0.85, (X0 + X1) / 2, X1 - 0.85):
            b.box(xs - 0.09, xs + 0.09, yb - 0.004, yb + 0.02, 0.05, 0.10, "interior")
        b.box(X0 + wt, X1 - wt, yb + wt, ya, h - 0.30, h - 0.05, "земля")
        for (cx, cy, rx, ry) in ((X0 + 0.8, yb + 0.30, 0.34, 0.20), (X1 - 0.9, yb + 0.40, 0.40, 0.22)):
            b.sphere(cx, cy, h - 0.05, rx, ry, 0.045, "земля", sub=1)
    nob = b.build()
    old = ob.data
    ob.data = nob.data
    bpy.data.meshes.remove(old)
    for m in list(ob.data.materials):
        pass
    ob.data.materials.clear()
    for nme in b.mats:
        ob.data.materials.append(kit.get_mat(nme))


PADLOCK = "E:/Models Blender/PROPS/Padlock_01/models/padlock_v05_textured.blend"


def load_padlock():
    """Готовый замок владельца (padlock_v05_textured.blend, корпус 80 × 24,5 × 120 мм): коллекция с материалами и встроенными картами
    подключается копией (append), сам файл не правится; берём корень и его потомков, камеры и подложку студии отбрасываем."""
    with bpy.data.libraries.load(PADLOCK, link=False) as (src, dst):
        dst.collections = ["PADLOCK | geometry candidate"]
    big = dst.collections[0]
    root = bpy.data.objects.get("Padlock_ROOT")
    keep = {root} | set(root.children_recursive)
    col = bpy.data.collections.new("Padlock_owner")
    for ob in list(big.objects):
        if ob in keep and ob.type in ("MESH", "EMPTY"):
            col.objects.link(ob)
    sh = bpy.data.objects["Shackle_forged_closed"]
    pts = [sh.matrix_world @ Vector(c) for c in sh.bound_box]
    cx = sum(p.x for p in pts) / 8
    cy = sum(p.y for p in pts) / 8
    ztop = max(p.z for p in pts)
    return col, Vector((cx, cy, ztop - 0.0062))


def hang_lock(asm, col, bar, target, rotz, name):
    """Замок вешается дужкой на точку target (мир): верхняя перемычка дужки в этой точке, лицо — по повороту."""
    from mathutils import Matrix
    e = bpy.data.objects.new(name, None)
    e.instance_type = "COLLECTION"
    e.instance_collection = col
    R = Matrix.Rotation(rotz, 3, "Z")
    e.location = target - R @ bar
    e.rotation_euler = (0, 0, rotz)
    asm.objects.link(e)
    return e


def link_mesh():
    """Звено цепи: пруток 6 мм по контуру «стадиона» 40 × 25 мм."""
    me = bpy.data.meshes.new("chain_link")
    bm = bmesh.new()
    pts = []
    R, S = 0.0095, 0.0075
    for k in range(9):
        a = -math.pi / 2 + math.pi * k / 8
        pts.append((S + R * math.cos(a), R * math.sin(a)))
    for k in range(9):
        a = math.pi / 2 + math.pi * k / 8
        pts.append((-S + R * math.cos(a), R * math.sin(a)))
    n = len(pts)
    rings = []
    for i, (px, py) in enumerate(pts):
        nx, ny = pts[(i + 1) % n][0] - pts[i - 1][0], pts[(i + 1) % n][1] - pts[i - 1][1]
        L = math.hypot(nx, ny)
        tx, ty = nx / L, ny / L
        ox, oy = ty, -tx                                   # в плоскости, наружу
        ring = []
        for q in range(6):
            t = 2 * math.pi * q / 6
            ring.append(bm.verts.new((px + ox * 0.003 * math.cos(t), py + oy * 0.003 * math.cos(t), 0.003 * math.sin(t))))
        rings.append(ring)
    for i in range(n):
        for q in range(6):
            bm.faces.new((rings[i][q], rings[i][(q + 1) % 6], rings[(i + 1) % n][(q + 1) % 6], rings[(i + 1) % n][q]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for f in me.polygons:
        f.use_smooth = True
    me.materials.append(MT.get("chain_steel"))
    return me


def security():
    """Дом заброшен, вход закрыт дёшево: цепь с навесным замком на ручках дверей, лист-объявление на стекле изнутри,
    навесной замок на проушинах служебной двери."""
    import kit
    from mathutils import Matrix
    asm = bpy.data.collections["Дом7_сборка"]
    me = link_mesh()
    yc = -12.62
    path = []
    for k in range(401):
        th = 5 * math.pi * k / 400.0
        path.append(Vector((-1.0 + 0.19 * math.cos(th), yc + 0.05 * math.sin(th), 1.10 + 0.04 * th / (2 * math.pi))))
    # начальный конец тоже свисает вниз (раньше торчал горизонтально): дуга радиуса 5 см от витка и вертикальный хвост
    p0 = path[0]
    head = []
    for k in range(1, 9):
        a = math.pi / 2 * k / 8.0
        head.append(Vector((p0.x + 0.012 * (1 - math.cos(a)), p0.y - 0.05 * math.sin(a), p0.z - 0.05 * (1 - math.cos(a)))))
    for k in range(1, 31):
        t = k / 30.0
        head.append(Vector((p0.x + 0.012, p0.y - 0.05, p0.z - 0.05 - 0.26 * t)))
    path = head[::-1] + path
    end = path[-1]
    for k in range(1, 41):                                  # свободный конец свисает вниз
        t = k / 40.0
        path.append(Vector((end.x - 0.012 * t, end.y - 0.03 * math.sin(math.pi * t * 0.5), end.z - 0.40 * t)))
    cum = [0.0]
    for i in range(1, len(path)):
        cum.append(cum[-1] + (path[i] - path[i - 1]).length)
    pitch = 0.0275
    nl = int(cum[-1] / pitch)
    j = 0
    for i in range(nl):
        sdist = i * pitch
        while j < len(path) - 2 and cum[j + 1] < sdist:
            j += 1
        p = path[j].lerp(path[j + 1], (sdist - cum[j]) / max(cum[j + 1] - cum[j], 1e-9))
        tg = (path[j + 1] - path[j]).normalized()
        up = Vector((0, 0, 1))
        side = tg.cross(up)
        if side.length < 1e-3:
            side = Vector((1, 0, 0))
        side.normalize()
        nrm = side if i % 2 == 0 else tg.cross(side).normalized()
        if i == nl - 1:
            nrm = Vector((0, 1, 0))
        zax = tg.cross(nrm).normalized()
        rot = Matrix(((tg.x, nrm.x, zax.x), (tg.y, nrm.y, zax.y), (tg.z, nrm.z, zax.z)))
        ob = bpy.data.objects.new("chain_%d" % i, me)
        ob.matrix_world = Matrix.Translation(p) @ rot.to_4x4()
        ob.visible_glossy = False                           # в стекле дверей не отражается чёрным дублем (в игре его тоже нет)
        last_link = (p, tg)
        asm.objects.link(ob)
    # замок владельца: дужка продета в последнее звено, висит лицом наружу (−Y)
    pcol, pbar = load_padlock()
    for pob in pcol.objects:
        pob.visible_glossy = False
    # дужка — во внутреннем нижнем конце последнего звена (раньше замок висел на конце пути, на ~5 см ниже звена)
    lp, ltg = last_link
    tip = lp + ltg * (0.0095 + 0.0075 - 0.006)
    hang_lock(asm, pcol, pbar, Vector((tip.x, tip.y, tip.z)), 0.0, "padlock_chain")
    # лист-объявление А4 в файле: пятиугольник с загнутым углом, скотч, прозрачный файл
    yn = -12.448
    x0, x1, z0, z1, fo = -1.95, -1.74, 1.56, 1.857, 0.04
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    def quad(pts, uvs, mi):
        f = bm.faces.new([bm.verts.new(p) for p in pts])
        f.material_index = mi
        for l, uv in zip(f.loops, uvs):
            l[uvl].uv = uv
    quad([(x0, yn, z1), (x0, yn, z0), (x1, yn, z0), (x1, yn, z1 - fo)], [(0, 1), (0, 0), (1, 0), (1, 1 - fo / (z1 - z0))], 0)
    # недостающая верхняя кромка: треугольник между (x0,z1), (x1,z1-fo) и верхним краем
    tri = bm.faces.new([bm.verts.new(p) for p in ((x0, yn, z1), (x1, yn, z1 - fo), (x1 - fo, yn, z1))])
    tri.material_index = 0
    for l, uv in zip(tri.loops, ((0, 1), (1, 1 - fo / (z1 - z0)), (1 - fo / (x1 - x0), 1))):
        l[uvl].uv = uv
    fold = bm.faces.new([bm.verts.new(p) for p in ((x1 - fo, yn - 0.004, z1), (x1, yn - 0.004, z1 - fo), (x1 - fo, yn - 0.010, z1 - fo))])
    fold.material_index = 0
    for l, uv in zip(fold.loops, ((0.9, 0.02), (0.98, 0.02), (0.9, 0.06))):
        l[uvl].uv = uv
    nme = bpy.data.meshes.new("notice")
    bm.to_mesh(nme)
    bm.free()
    nme.materials.append(MT.get("notice"))
    for f in nme.polygons:
        f.use_smooth = False
    asm.objects.link(bpy.data.objects.new("notice", nme))
    tb = kit.B("notice_tape")
    for xt in (x0 + 0.01, x1 - 0.045):
        tb.box(xt, xt + 0.040, yn - 0.003, yn - 0.001, z1 - 0.012, z1 + 0.010, "steel")
    tob = tb.build()
    tob.data.materials.clear()
    tob.data.materials.append(MT.get("tape"))
    asm.objects.link(tob)
    sb = kit.B("notice_sleeve")
    sb.box(x0 - 0.010, x1 + 0.010, yn - 0.007, yn - 0.0055, z0 - 0.01, z1 + 0.02, "steel")
    sob = sb.build()
    sob.data.materials.clear()
    sob.data.materials.append(MT.get("sleeve"))
    asm.objects.link(sob)
    # служебная дверь (север): накладка с проушиной на полотне и на коробке + навесной замок; координаты модуля → мир (поворот 180°)
    hb = kit.B("door_hasp")
    # в локальных осях модуля: наружу = −y, лицо полотна y = 0.21, ширина поля 2,5, замок со стороны ручки (lx1 = 1,835)
    hb.box(1.665, 1.775, 0.185, 0.212, 0.98, 1.06, "steel", bev=0.003)          # накладка на полотне
    hb.box(1.80, 1.90, 0.135, 0.165, 0.98, 1.06, "steel", bev=0.003)             # проушина на коробке
    hb.box(1.745, 1.775, 0.150, 0.190, 1.005, 1.035, "steel", bev=0.002)         # петля накладки
    hob = hb.build()
    hob.matrix_world = Matrix.Translation((1.25, 13.0, 0.0)) @ Matrix.Rotation(math.pi, 4, "Z")
    asm.objects.link(hob)
    hang_lock(asm, pcol, pbar, Vector((1.25 - 1.775, 13.0 - 0.150, 1.02)), math.pi, "padlock_door")


def fix_canopy():
    """Плита козырька вдвинута внутрь лобовой балки на 1 см: совпадающие грани двух коробок давали чёрный «кубик» на торце."""
    ob = bpy.data.collections["H7_PortalCanopy"].objects[0]
    for v in ob.data.vertices:
        if v.co.y < -15.3 and 4.15 < v.co.z < 4.55:
            v.co.y += 0.012
            if abs(v.co.x) > 6.5:
                v.co.x -= 0.012 * (1 if v.co.x > 0 else -1)


def assign_materials():
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        ov = OVER.get(ob.name, {})
        for slot in ob.material_slots:
            m = slot.material
            if not m:
                continue
            nm = ov.get(m.name, m.name)
            if nm in MT.MATS:
                slot.material = MT.get(nm)
        if ob.name == "H7_Roof":                          # надстройки — оцинковка, покрытие кровли — рулонное
            slots = [s.material.name if s.material else "" for s in ob.material_slots]
            gi = None
            for i, nme in enumerate(slots):
                if nme.startswith("steel"):
                    gi = i
            if gi is None:
                ob.data.materials.append(MT.get("galvanized"))
                gi = len(ob.data.materials) - 1
            dk = [i for i, nme in enumerate(slots) if nme.startswith("roof_membrane")]
            for p in ob.data.polygons:
                if p.center.z > H_ROOF + 0.3 and p.material_index in dk:
                    p.material_index = gi
        if ob.name == "H7_PortalBeds":
            pass


# ------------------------------------------------------------------ декали
def plane(col, name, p0, p1, p2, p3, uv, mat):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in (p0, p1, p2, p3)]
    f = bm.faces.new(vs)
    layer = bm.loops.layers.uv.new("UVMap")
    (u0, v0, u1, v1) = uv
    for l, (u, v) in zip(f.loops, ((u0, v1), (u1, v1), (u1, v0), (u0, v0))):
        l[layer].uv = (u, v)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.visible_shadow = False
    col.objects.link(ob)
    return ob


def decals(root):
    col = bpy.data.collections.new("Декали")
    root.children.link(col)
    rng = random.Random(5)
    dark = MT.decal_mat("decal_dark", "masks/m_grain.png", (0.05, 0.045, 0.04, 1), 2.6)
    lime = MT.decal_mat("decal_lime", "masks/m_grain.png", MT.lin((170, 165, 155)) + (1,), 1.6)
    grime = MT.decal_mat("decal_grime", "masks/m_plaque.png", (0.06, 0.05, 0.04, 1), 0.6)
    cap = MT.decal_mat("decal_cap", "masks/m_smear.png", (0.07, 0.06, 0.05, 1), 0.45)

    def face_plane(face, name, u0, u1, z0, z1, off, uvr, mat):
        """Плоскость вдоль фасада: S (y<0) и N (y>0) — по x; E и W — по y; off — вынос от плоскости фасада."""
        if face == "S":
            a, b = (u0, -HY - off, z0), (u1, -HY - off, z1)
            return plane(col, name, (u0, -HY - off, z1), (u1, -HY - off, z1), (u1, -HY - off, z0), (u0, -HY - off, z0), uvr, mat)
        if face == "N":
            return plane(col, name, (u1, HY + off, z1), (u0, HY + off, z1), (u0, HY + off, z0), (u1, HY + off, z0), uvr, mat)
        if face == "E":
            return plane(col, name, (18 + off, u1, z1), (18 + off, u0, z1), (18 + off, u0, z0), (18 + off, u1, z0), uvr, mat)
        return plane(col, name, (-18 - off, u0, z1), (-18 - off, u1, z1), (-18 - off, u1, z0), (-18 - off, u0, z0), uvr, mat)

    asm = bpy.data.collections["Дом7_сборка"]
    n = 0
    for o in asm.objects:
        m = o.get("module", "")
        if o.name[:1] not in ("S", "N") or not (m.startswith("H_Window") or m.startswith("H_Loggia")):
            continue
        face = o.name[0]
        w = int(m.split("_")[-1]) / 1000.0
        z0 = o.location.z
        cx = o.location.x + (w / 2 if face == "S" else -w / 2)
        if m.startswith("H_Window"):
            if rng.random() > (0.35 if face == "S" else 0.6):
                continue
            L = rng.uniform(0.3, 2.0)
            wd = rng.uniform(1.2, 1.9)
            ztop = z0 + 0.57
        else:                                                   # потёки лоджий лежат на самих модулях (AO под полосой), декалью не дублируем
            continue
        u0, v0 = rng.random() * 0.4, rng.random() * 0.4
        uvr = (u0, v0, u0 + wd / 14.0, v0 + L / 2.0)
        face_plane(face, "dec_%s_%d" % ("win" if m.startswith("H_Window") else "log", n), cx - wd / 2, cx + wd / 2, ztop - L, ztop,
                   0.056, uvr, dark if rng.random() < 0.75 else lime)
        n += 1
    # под отливом-крышкой парапета: вся длина, плитка маски 3 м (UV больше 1)
    for face, a, b in (("S", -18, 18), ("N", -18, 18), ("E", -12.8, 12.8), ("W", -12.8, 12.8)):
        L = b - a
        face_plane(face, "dec_cap_" + face, a, b, H_ROOF - 2.0, H_ROOF, 0.004, (0.0, 0.2, L / 3.0, 0.2 + 2.0 / 3.0), cap)
    # под капителями пилястр и у цоколя
    for u in (-14.75, -11.75, -8.75, 8.75, 11.75, 14.75):
        uu = rng.random() * 0.5
        face_plane("S", "dec_pil_S%.1f" % u, u - 0.3, u + 0.3, 4.5 - 1.6, 4.5 - 0.05, 0.456, (uu, 0.1, uu + 0.5, 0.65), dark)
        face_plane("S", "dec_efl_S%.1f" % u, u - 0.25, u + 0.25, 4.5 - 1.0, 4.5 - 0.2, 0.458, (uu + 0.2, 0.3, uu + 0.65, 0.7), lime)
    for i in range(12):
        u = -16.5 + 3.0 * i
        uu = rng.random() * 0.5
        face_plane("N", "dec_pil_N%d" % i, u - 0.3, u + 0.3, 4.5 - 1.6, 4.5 - 0.05, 0.456, (uu, 0.1, uu + 0.5, 0.65), dark)
    for face, runs in (("S", ((-17.5, -7.0), (7.0, 17.5))), ("N", ((-17.5, 17.5),)), ("E", ((-12.5, 12.5),)), ("W", ((-12.5, 12.5),))):
        for (a, b) in runs:
            face_plane(face, "dec_belt_" + face, a, b, 2.8, 4.5, 0.006, (rng.random() * 0.3, 0.3, rng.random() * 0.3 + (b - a) / 3.0, 0.3 + 1.7 / 3.0), grime)


# ------------------------------------------------------------------ растения
def blade(bm, base, ang, H, w0, lean, mat_i, nseg=4):
    d = Vector((math.cos(ang), math.sin(ang), 0))
    side = Vector((-d.y, d.x, 0))
    pts = []
    for i in range(nseg + 1):
        t = i / nseg
        c = base + d * (lean * t * t) + Vector((0, 0, H * t * (1.0 - 0.12 * t)))
        w = w0 * (1.0 - t * 0.92)
        pts.append((c - side * w, c + side * w))
    prev = None
    for (a, b) in pts:
        va, vb = bm.verts.new(a), bm.verts.new(b)
        if prev:
            f = bm.faces.new((prev[0], prev[1], vb, va))
            f.material_index = mat_i
        prev = (va, vb)


def tuft(bm, cx, cy, z, n, hmin, hmax, rng, rad=0.10, dry=0.25, flowers=0.0):
    fl = []
    for _ in range(n):
        ang = rng.uniform(0, math.tau)
        a2 = rng.uniform(0, math.tau)
        r = rng.uniform(0, rad)
        base = Vector((cx + r * math.cos(a2), cy + r * math.sin(a2), z))
        H = rng.uniform(hmin, hmax)
        blade(bm, base, ang, H, rng.uniform(0.008, 0.016), rng.uniform(0.1, 0.45) * H, 1 if rng.random() < dry else 0)
        if flowers and rng.random() < flowers:
            fl.append(base + Vector((math.cos(ang) * 0.2 * H, math.sin(ang) * 0.2 * H, H * 0.88)))
    for p in fl:
        r = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.014)
        for v in r["verts"]:
            v.co += p
            for f in v.link_faces:
                f.material_index = 2


def plants(root):
    old = bpy.data.collections.get("Растения_заглушки")
    if old:
        for ob in list(old.objects):
            bpy.data.objects.remove(ob)
        old.name = "Растения"
    col = old or bpy.data.collections.new("Растения")
    if not old:
        root.children.link(col)
    rng = random.Random(21)
    me = bpy.data.meshes.new("weeds")
    bm = bmesh.new()
    for m in ("weed_green", "weed_dry", "weed_flower"):
        me.materials.append(MT.get(m))
    X0, X1 = 2.3, 5.7
    terr = ((1.35, -13.0, -13.7), (0.90, -13.7, -14.4), (0.45, -14.4, -15.1))
    for k, (h, ya, yb) in enumerate(terr):
        zs = h - 0.06
        yc = (ya + yb) / 2
        for i in range(9):                                                           # злаки и сорняки выше культурных
            tuft(bm, X0 + 0.3 + 0.36 * i + rng.uniform(-0.1, 0.1), yc + rng.uniform(-0.2, 0.2), zs, 46, 0.3, 0.95, rng, 0.14, 0.3, 0.04)
        for i in range(5):                                                           # низкая густая трава
            tuft(bm, X0 + 0.4 + 0.65 * i, yc + rng.uniform(-0.2, 0.2), zs, 30, 0.1, 0.32, rng, 0.2, 0.15)
        if k == 2:
            for i in range(7):                                                       # свисающее через борт
                bx = X0 + 0.35 + 0.46 * i
                for _ in range(6):
                    base = Vector((bx + rng.uniform(-0.1, 0.1), yb + 0.1, h))
                    ang = math.pi * 1.5 + rng.uniform(-0.4, 0.4)
                    blade(bm, base, ang, -rng.uniform(0.1, 0.3), 0.012, rng.uniform(0.15, 0.4), 0)
    # редкие сорняки в швах цоколя и на козырьке
    for _ in range(90):
        t = rng.uniform(0, 1)
        side = rng.choice("SNEW")
        if side in "SN":
            x = rng.uniform(-17.4, 17.4)
            if side == "S" and -7.5 < x < 7.5:
                continue
            y = (-13.02 - rng.uniform(0.0, 0.12)) if side == "S" else (13.02 + rng.uniform(0.0, 0.12))
        else:
            y = rng.uniform(-12.4, 12.4)
            x = (18.02 + rng.uniform(0.0, 0.12)) if side == "E" else (-18.02 - rng.uniform(0.0, 0.12))
        tuft(bm, x, y, 0.012, rng.randint(5, 12), 0.08, 0.30, rng, 0.04, 0.4, 0.08)
    for _ in range(8):
        tuft(bm, rng.uniform(-6.5, 6.5), -14.9 + rng.uniform(-0.3, 0.3), 4.65, 8, 0.06, 0.18, rng, 0.05, 0.4)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("weeds", me)
    col.objects.link(ob)
    # кустарник: своя сирень проекта (lilac_c), уменьшена до 0,9 м
    try:
        with bpy.data.libraries.load(PLANTS, link=False) as (src, dst):
            dst.collections = ["lilac_c"]
        lc = dst.collections[0]
        lc.instance_offset = (14.6, 0.0, 0.0)
        for (x, y, h, s, r) in ((3.0, -13.35, 1.30, 0.34, 0.5), (5.1, -14.05, 0.85, 0.30, 2.1), (3.4, -14.75, 0.40, 0.26, 4.0)):
            e = bpy.data.objects.new("lilac_inst", None)
            e.instance_type = "COLLECTION"
            e.instance_collection = lc
            e.location = (x, y, h)
            e.scale = (s, s, s)
            e.rotation_euler = (0, 0, r)
            col.objects.link(e)
    except Exception as ex:
        print("lilac failed", ex)


# ------------------------------------------------------------------ мир, свет, камеры
def world_and_light():
    sc = bpy.context.scene
    w = bpy.data.worlds.new("overcast_hdri")
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(HDRI)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 1.1
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(env.outputs[0], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])
    sc.world = w
    fo = bpy.data.objects.get("fill_up")
    if fo:
        bpy.data.objects.remove(fo)
    sun = bpy.data.objects["sun"]
    sun.data.energy = 2.2
    sun.data.color = (1.0, 0.95, 0.88)
    sun.data.angle = math.radians(30)                                  # пасмурно: тени мягкие, под козырьком резкой тени нет
    if os.environ.get("HOUSE7_NOSUN"):
        sun.data.energy = 0.0
    sun.rotation_euler = (math.radians(58), 0, math.radians(-40))
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.max_bounces = 8
    sc.cycles.transparent_max_bounces = 12
    sc.cycles.transmission_bounces = 8
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.exposure = 0.3
    cams = {"cam_eye6": ((-1.0, -19.5, 1.7), (-1.0, -13.0, 2.7), 24),
            "cam_loggia_close": ((-6.2, -21.5, 13.2), (-6.2, -13.0, 14.6), 35),
            "cam_chain": ((-1.5, -14.3, 1.05), (-1.1, -12.62, 0.98), 32),
            "cam_service_door": ((0.2, 19.0, 1.5), (0.1, 13.0, 1.15), 30)}
    prev = bpy.data.collections["Просмотр"]
    for n, (loc, tgt, lens) in cams.items():
        cd = bpy.data.cameras.new(n)
        cd.lens = lens
        cd.clip_end = 600
        co = bpy.data.objects.new(n, cd)
        co.location = loc
        co.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        prev.objects.link(co)


def render(prev_dir, only, res, samples):
    sc = bpy.context.scene
    os.makedirs(prev_dir, exist_ok=True)
    sc.cycles.samples = samples
    kset = bpy.data.collections["Набор_частей"]
    kset.hide_render = True
    names = ["cam_court", "cam_court_sw", "cam_avenue", "cam_north_east", "cam_end_east", "cam_end_west", "cam_portal", "cam_planter",
             "cam_plinth", "cam_loggia", "cam_eye6", "cam_loggia_close", "cam_chain", "cam_service_door", "ortho_south"]
    for n in names:
        if only and n not in only:
            continue
        sc.camera = bpy.data.objects[n]
        if n.startswith("ortho"):
            sc.render.resolution_x, sc.render.resolution_y = 1100, 1000
        else:
            sc.render.resolution_x, sc.render.resolution_y = res
        bpy.data.objects["preview_police"].hide_render = (n != "cam_avenue")
        sc.render.filepath = os.path.join(prev_dir, n + ".png")
        bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out = argv[0]
    prev_dir = argv[argv.index("preview") + 1] if "preview" in argv else None
    only = argv[argv.index("only") + 1].split(",") if "only" in argv else None
    res = tuple(int(x) for x in argv[argv.index("res") + 1].split("x")) if "res" in argv else (1400, 875)
    samples = int(argv[argv.index("samples") + 1]) if "samples" in argv else 64
    bpy.ops.wm.open_mainfile(filepath=FORM)
    rebuild_beds()
    vestibule()
    rebuild_curtains()
    security()
    fix_canopy()
    assign_materials()
    root = bpy.context.scene.collection
    decals(root)
    plants(root)
    world_and_light()
    bpy.ops.wm.save_as_mainfile(filepath=out, relative_remap=True)
    try:
        bpy.ops.file.make_paths_relative()
        bpy.ops.wm.save_mainfile()
    except Exception as ex:
        print("relative paths", ex)
    print("saved", out)
    if prev_dir:
        render(prev_dir, only, res, samples)


main()
