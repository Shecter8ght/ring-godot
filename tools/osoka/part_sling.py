# «Осока»: ремень — серая лямка от передней петли (левый бок накладки) через верх накладки и по верху трубы к задней
# антабке; наплечная подушка (снимок КБМ: ремень поднят над трубой на x 1250…1640 пикс), пряжка спереди сверху.
import math
import bmesh
import bpy
from mathutils import Vector
from lib import MM, _obj, fillet, rounded_prism, px_x, pchip
import dims as D

W, T = 30.0, 2.2          # ширина и толщина лямки (оценка: стропа 30 мм)


def strap_path():
    top = D.SADDLE_TOP + T / 2 + 0.2
    tube_top = D.TUBE_R + T / 2 + 0.2
    clamp_top = D.CLAMP_R + T / 2 + 0.2
    pts = [
        (1318.0, D.SADDLE_LEFT + 7.0, 22.0),       # из петли
        (1314.0, D.SADDLE_LEFT + 5.0, 36.0),
        (1306.0, D.SADDLE_LEFT - 4.0, top + 1.0),
        (1296.0, 20.0, top),
        (1280.0, 0.0, top),
        (1180.0, -4.0, top),
        (1165.0, -4.0, top - 3.0),
        (1135.0, -4.0, clamp_top),
        (1000.0, -4.0, clamp_top),
        (960.0, -4.0, tube_top + 1.5),
        (900.0, -4.0, tube_top + 3.0),          # под подушкой
        (640.0, -4.0, tube_top + 3.0),
        (606.0, -4.0, D.SLING_BAND[2] + 6.0),
        (588.0, -4.0, D.SLING_BAND[2] + 8.5),   # к ушку антабки
    ]
    return [Vector(p) for p in pts]


def resample(pts, step=4.0):
    # сглаживание ломаной: Катмулл — Ром, затем равный шаг
    out = []
    n = len(pts)
    for i in range(n - 1):
        p0 = pts[max(i - 1, 0)]; p1 = pts[i]; p2 = pts[i + 1]; p3 = pts[min(i + 2, n - 1)]
        L = (p2 - p1).length
        k = max(2, int(L / step))
        for j in range(k):
            t = j / k
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(pts[-1])
    return out


def sweep_strap(name, path, w, t, coll, mat):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = []
    hw, ht = w / 2, t / 2
    # сечение лямки — прямоугольник со скруглёнными краями (8 точек)
    sec = [(-hw, -ht * 0.6), (-hw + 0.6, -ht), (hw - 0.6, -ht), (hw, -ht * 0.6), (hw, ht * 0.6), (hw - 0.6, ht),
           (-hw + 0.6, ht), (-hw, ht * 0.6)]
    for i, p in enumerate(path):
        a = path[max(i - 1, 0)]; b = path[min(i + 1, len(path) - 1)]
        tang = (b - a).normalized()
        # нормаль толщины — от оси трубы наружу (лямка лежит на поверхности)
        radial = Vector((0.0, p.y, p.z))
        if radial.length < 1e-6:
            radial = Vector((0, 0, 1))
        nrm = (radial - tang * radial.dot(tang)).normalized()
        side = tang.cross(nrm).normalized()
        rings.append([bm.verts.new((p + side * sx + nrm * sy) * MM) for sx, sy in sec])
    m = len(sec)
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(m):
            j = (k + 1) % m
            bm.faces.new((r0[k], r0[j], r1[j], r1[k]))
    bm.faces.new(list(reversed(rings[0]))); bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    return _obj(name, me, coll, mat)


def build(ctx):
    C = ctx["coll"]["Sling"]
    path = resample(strap_path(), 3.0)
    strap = sweep_strap("Sling_strap", path, W, T, C, "Webbing_grey")
    # наплечная подушка — мягкая серая накладка поверх лямки (X 650…900)
    zt = D.TUBE_R + 0.6
    pts = fillet([(650.0, zt), (900.0, zt), (900.0, zt + 9.0), (650.0, zt + 9.0)], [3.5, 3.5, 4.5, 4.5], seg=5)
    pad = rounded_prism("Sling_pad", pts, -27.0, 19.0, 3.4, C, "Webbing_grey")
    # пряжка-рамка спереди сверху (снимок: 630…690 пикс)
    xa, xb = px_x(690), px_x(630)
    zt2 = D.SADDLE_TOP + 0.3
    frame_out = fillet([(xa, -22.0), (xb, -22.0), (xb, 14.0), (xa, 14.0)], [3.0] * 4, seg=4)
    import lib
    buckle = lib.prism_xy("Sling_buckle", frame_out, zt2, zt2 + 4.0, C, "Steel_black")
    hole = lib.prism_xy("_bh", fillet([(xa + 3.5, -18.5), (xb - 3.5, -18.5), (xb - 3.5, 10.5), (xa + 3.5, 10.5)], [1.5] * 4, seg=4),
                        zt2 - 1.0, zt2 + 5.0, C)
    lib.boolean(buckle, hole)
    # перемычка пряжки поперёк
    bar = lib.prism_xy("Sling_buckle_bar", fillet([(0.5 * (xa + xb) - 1.5, -18.6), (0.5 * (xa + xb) + 1.5, -18.6),
                                                   (0.5 * (xa + xb) + 1.5, 10.6), (0.5 * (xa + xb) - 1.5, 10.6)], [0.8] * 4, seg=3),
                       zt2 + 0.2, zt2 + 3.8, C, "Steel_black")
    lib.finish_small(buckle, 0.6, 2, 40)
    lib.finish_small(bar, 0.5, 2, 40)
    return {"strap": strap, "pad": pad}
