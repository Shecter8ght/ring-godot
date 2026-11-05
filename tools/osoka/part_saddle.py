# «Осока»: накладка трубы над пусковым механизмом («седло») — литой корпус вокруг трубы, круглые крышки (слева на
# хомуте ГСН, слева и сверху на накладке), откидная прямоугольная крышка сверху спереди, мушка-рамка и целик со
# световым индикатором (слева — глаз стрелка у левого бока трубы), передняя петля ремня. Контуры — снимок КБМ (dims.py).
import math
import bmesh
import bpy
from mathutils import Matrix, Vector
from lib import (MM, v, lathe, loft_yz, rounded_prism, finish, finish_small, fillet, px, px_x, px_z, _obj,
                 apply_transform, set_origin, cyl, material)
import dims as D

SADDLE_REAR_X = px_x(776)          # задний торец накладки (снимок: 776 пикс)


def section(top, left, right_top, bottom, r_top=15.0, r_bot=7.0):
    """Сечение накладки: верх и левый бок, справа — только край верха (труба справа открыта, снимки 04, 05).
    Замыкание идёт через канал трубы — его потом вычитает обжатие по трубе."""
    pts = [(right_top, 30.0), (right_top, top), (left, top), (left, bottom), (0.0, bottom), (-6.0, -28.0)]
    return fillet(pts, [0.0, 3.0, r_top, r_bot, 0.0, 0.0], seg=8)


def saddle(coll):
    x0, x1 = SADDLE_REAR_X, D.SADDLE_X[1]
    sec = section(D.SADDLE_TOP, D.SADDLE_LEFT, D.SADDLE_RIGHT_TOP, D.SADDLE_BOTTOM)
    o = loft_yz("Saddle_body", [(x0, sec), (x1, sec)], coll, "Paint_olive_cast")
    finish(o, w=1.6, seg=4, angle=30)
    return o


def arc_shell(name, x0, x1, r_in, r_out, a0, a1, coll, mat, seg=48):
    """Полка вокруг трубы: кольцевой сектор от угла a0 до a1 (град, от +Y к +Z), вытянутый по X."""
    pts = []
    for k in range(seg + 1):
        a = math.radians(a0 + (a1 - a0) * k / seg)
        pts.append((r_out * math.cos(a), r_out * math.sin(a)))
    for k in range(seg + 1):
        a = math.radians(a1 - (a1 - a0) * k / seg)
        pts.append((r_in * math.cos(a), r_in * math.sin(a)))
    o = loft_yz(name, [(x0, pts), (x1, pts)], coll, mat)
    finish(o, w=0.7, seg=3, angle=30)
    return o


def right_flange(coll):
    """Полка литья по низу трубы справа с винтами (снимок 05: горизонтальная полка, винты, бобышка с отверстием)."""
    from part_launcher import slotted_screw
    x0, x1 = D.RIGHT_FLANGE_X
    a0, a1 = D.RIGHT_FLANGE_ANG
    fl = arc_shell("Saddle_right_flange", x0, x1, D.TUBE_R + 0.1, D.TUBE_R + 3.4, a0, a1, coll, "Paint_olive_cast")
    out = [fl]
    am = math.radians(0.5 * (a0 + a1) - 8.0)
    n = Vector((0.0, math.cos(am), math.sin(am)))
    for i, x in enumerate((x0 + 22.0, x0 + 90.0, x0 + 160.0, x1 - 30.0)):
        c = Vector((x, 0, 0)) + n * (D.TUBE_R + 3.4)
        out.append(slotted_screw(f"Saddle_right_screw_{i}", tuple(c), tuple(n), 5.0, coll, "Paint_olive_cast",
                                 slot_ang=25 * i))
    # бобышка с отверстием (снимок 05: прямоугольный прилив на полке ближе к коробу)
    from lib import box as box_
    bx = x0 + 45.0
    pts = fillet([(bx - 13.0, -24.0), (bx + 13.0, -24.0), (bx + 13.0, -8.0), (bx - 13.0, -8.0)], [3.0] * 4, seg=4)
    boss = rounded_prism("Saddle_right_boss", pts, -D.TUBE_R - 6.0, -D.TUBE_R + 4.0, 1.2, coll, "Paint_olive_cast")
    out.append(boss)
    return out


def front_right_plate(coll):
    """Накладка на четырёх винтах справа спереди, за хомутом ГСН (снимки 04, 05)."""
    from part_launcher import slotted_screw
    x0, x1 = D.FRONT_RIGHT_PLATE_X
    pts = fillet([(x0, -20.0), (x1, -20.0), (x1, 16.0), (x0, 16.0)], [4.0] * 4, seg=4)
    boss = rounded_prism("Front_right_boss", pts, -D.TUBE_R - 5.0, -D.TUBE_R + 6.0, 2.0, coll, "Paint_olive_cast")
    pts2 = fillet([(x0 + 2.5, -17.5), (x1 - 2.5, -17.5), (x1 - 2.5, 13.5), (x0 + 2.5, 13.5)], [3.0] * 4, seg=4)
    plate = rounded_prism("Front_right_plate", pts2, -D.TUBE_R - 7.0, -D.TUBE_R - 4.5, 0.8, coll, "Paint_olive_cast")
    out = [boss, plate]
    for i, (dx, dz) in enumerate(((5.5, -12.0), (x1 - x0 - 5.5, -12.0), (5.5, 8.0), (x1 - x0 - 5.5, 8.0))):
        out.append(slotted_screw(f"Front_right_screw_{i}", (x0 + dx, -D.TUBE_R - 7.0, dz), (0, -1, 0), 4.6, coll,
                                 "Paint_olive_cast", slot_ang=40 * i))
    return out


def mount_plate(coll):
    """Основание ночного прицела сверху — низкая длинная площадка за верхней крышкой (снимок 03)."""
    x0, x1 = D.MOUNT_PLATE_X
    zt = D.SADDLE_TOP
    pts = fillet([(x0, zt - 3.0), (x1, zt - 3.0), (x1, zt + 3.6), (x0, zt + 3.6)], [1.6, 1.6, 2.2, 2.2], seg=4)
    o = rounded_prism("Mount_plate", pts, -11.0, 15.0, 1.4, coll, "Paint_olive_cast")
    return [o]


def knurled_lid(name, d, h, coll, notches=10, depth=1.2):
    """Крышка с выемками по ободу (как на снимках): ось +X, от x = 0 (основание) до h."""
    from part_tube import lathe_mod
    R = d / 2

    def rfun(x, a, r):
        if r < R - 0.01 or x > h - 1.0 or x < 0.6:
            return r
        ph = (a * notches / (2 * math.pi)) % 1.0
        dd = min(abs(ph - 0.5) / 0.14, 1.0)
        return r - depth * (0.5 * (1 + math.cos(math.pi * dd)) if dd < 1.0 else 0.0)

    # торец — плоский диск с кольцами (без полюса-вмятины в центре): кольца радиусов до оси
    prof = [(0.0, 0.0), (0.0, R * 0.5), (0.0, R - 0.8), (0.4, R)]
    for k in range(1, 9):
        prof.append((0.4 + (h - 2.2) * k / 8, R))
    prof += [(h - 1.0, R - 0.4), (h - 0.3, R - 1.4), (h, R - 3.0), (h, R * 0.72), (h, R * 0.45), (h, R * 0.2),
             (h, 0.0)]
    o = lathe(name, prof, coll, "Paint_olive_cast", seg=120)
    # выемки по ободу — сдвиг вершин обода к оси
    for vv in o.data.vertices:
        x = vv.co.x / MM
        r = math.hypot(vv.co.y, vv.co.z) / MM
        if r > 1e-3:
            a = math.atan2(vv.co.z, vv.co.y)
            r2 = rfun(x, a, r)
            if r2 != r:
                vv.co.y *= r2 / r
                vv.co.z *= r2 / r
    return o


def lids(coll):
    out = []
    for name, x_px, y_px, d, side in D.LIDS:
        X = px_x(x_px)
        Z = px_z(x_px, y_px)
        if side == "L":
            base_y = 55.5 if name == "Lid_front" else D.SADDLE_LEFT - 0.5
            boss = cyl(name + "_boss", base_y - 14.0, base_y + 1.0, d / 2 - 3.0, coll, "Paint_olive_cast", seg=72,
                       cy=X, cz=Z, axis="Y", ch=0.8)
            cap = knurled_lid(name, d, 7.0, coll)
            # ось крышки +X → +Y (влево), основание на base_y
            cap.data.transform(Matrix.Rotation(math.pi / 2, 4, "Z"))
            cap.data.transform(Matrix.Translation(v(X, base_y + 1.0, Z)))
        else:
            boss = cyl(name + "_boss", D.SADDLE_TOP - 6.0, px_z(x_px, 346) + 0.3, 23.0, coll, "Paint_olive_cast", seg=72,
                       cy=X, cz=0.0, axis="Z", ch=0.8)
            cap = knurled_lid(name, d, px_z(x_px, 327) - px_z(x_px, 346), coll, notches=14, depth=0.9)
            cap.data.transform(Matrix.Rotation(-math.pi / 2, 4, "Y"))
            cap.data.transform(Matrix.Translation(v(X, 0.0, px_z(x_px, 346))))
        out += [boss, cap]
    return out


def dust_cover(coll):
    """Прямоугольная откидная крышка сверху спереди (ARES: отличие «Вербы» от «Иглы-С») — петля спереди, ось Y."""
    xa, xb = px_x(D.DUST_COVER_PX[1]), px_x(D.DUST_COVER_PX[0])     # 1459…1497
    zt = D.SADDLE_TOP
    base_pts = fillet([(xa - 2.0, zt - 6.0), (xb + 2.0, zt - 6.0), (xb + 2.0, zt + 3.5), (xa - 2.0, zt + 3.5)],
                      [2.0, 2.0, 3.0, 3.0], seg=4)
    base = rounded_prism("Dust_cover_base", base_pts, -17.0, 17.0, 1.5, coll, "Paint_olive_cast")
    lid_pts = fillet([(xa, zt + 3.5), (xb, zt + 3.5), (xb, zt + 8.5), (xa, zt + 8.5)], [1.8, 2.0, 2.4, 2.4], seg=4)
    lid = rounded_prism("Dust_cover", lid_pts, -15.0, 15.0, 1.6, coll, "Paint_olive_cast")
    # петля — валик у переднего края
    hinge = cyl("Dust_cover_hinge", -12.0, 12.0, 2.2, coll, "Paint_olive_cast", seg=24, cy=xb - 1.0, cz=zt + 4.2,
                axis="Y", ch=0.4)
    set_origin(lid, (xb - 1.0, 0.0, zt + 4.2))
    return [base, lid, hinge]


def front_sight(coll):
    """Мушка — чёрная рамка-кольцо с точкой на стойке, слева (снимок: x 331…412, y 370…427). Ось откидывания — по X у
    основания: сложенная ложится вниз-наружу вдоль борта."""
    xa, xb = px_x(D.FRONT_SIGHT_PX[1]), px_x(D.FRONT_SIGHT_PX[0])    # 1415…1469
    # ось откидывания — поперёк (по Y) у основания: сложенная ложится вперёд вдоль борта, кольцо не доходит до крышки
    hx, hy, hz = xb - 21.0, D.SADDLE_LEFT + 8.0, 9.0
    base_pts = fillet([(xa, -6.0), (hx + 5.0, -6.0), (hx + 5.0, hz + 1.5), (xa, hz + 1.5)], [2.0] * 4, seg=4)
    base = rounded_prism("Front_sight_base", base_pts, D.SADDLE_LEFT - 2.0, hy + 3.5, 1.2, coll, "Plastic_black")
    # стойка: от оси вверх к кольцу
    ring_c = (hx + 4.0, hy + 3.0, 27.0)
    post_pts = fillet([(hx - 1.0, hz - 3.0), (hx + 7.0, hz - 3.0), (hx + 7.0, ring_c[2] - 7.0), (hx - 1.0, ring_c[2] - 7.0)],
                      [1.5] * 4, seg=3)
    post = rounded_prism("Front_sight_post", post_pts, hy - 2.0, hy + 3.5, 0.9, coll, "Plastic_black")
    # кольцо-рамка: ось кольца по X (стрелок смотрит вдоль трубы), наружный Ø25, внутренний Ø19, толщина 4
    rr = lathe("Front_sight_ring", [(-2.0, 7.4), (-2.0, 10.0), (2.0, 10.0), (2.0, 7.4)], coll, "Plastic_black", seg=64)
    finish_small(rr, 0.5, 2, 40)
    rr.data.transform(Matrix.Translation(v(ring_c[0], ring_c[1], ring_c[2])))
    # точка мушки — тонкий столбик снизу кольца с шариком в центре
    pin = cyl("Front_sight_pin", ring_c[2] - 7.8, ring_c[2] - 0.6, 0.7, coll, "Plastic_black", seg=16, cy=ring_c[0],
              cz=ring_c[1], axis="Z")
    # cyl по Z: (cy, cz) — центр в X, Y
    dot = lathe("Front_sight_dot", [(-1.2, 0.0), (-1.0, 0.8), (0.0, 1.2), (1.0, 0.8), (1.2, 0.0)], coll, "Plastic_black",
                seg=24)
    dot.data.transform(Matrix.Translation(v(*ring_c)))
    leaf = [post, rr, pin, dot]
    from lib import join
    leaf_o = join(leaf, "Front_sight_leaf")
    set_origin(leaf_o, (hx, hy, hz))
    return [base, leaf_o]


def rear_sight(coll):
    """Целик со световым индикатором (снимок: x 725…777, y 305…422; кремовый колпачок индикатора 732…755 × 337…372,
    тонкое перо до y 305). Слева сверху за петлёй ремня; откидывается вниз-наружу по оси X у основания."""
    xa, xb = px_x(D.REAR_SIGHT_PX[1]), px_x(D.REAR_SIGHT_PX[0])      # 1170…1205
    hy, hz = D.SADDLE_LEFT - 6.0, 39.0
    base_pts = fillet([(xa, 20.0), (xb, 20.0), (xb, hz - 0.5), (xa, hz - 0.5)], [3.0] * 4, seg=4)
    base = rounded_prism("Rear_sight_base", base_pts, 30.0, D.SADDLE_LEFT - 2.0, 1.5, coll, "Plastic_black")
    body_pts = fillet([(xa + 4.0, hz + 0.5), (xb - 3.0, hz + 0.5), (xb - 3.0, 60.0), (xa + 4.0, 60.0)], [2.0] * 4, seg=4)
    body = rounded_prism("Rear_sight_body", body_pts, hy - 2.0, hy + 14.0, 1.6, coll, "Plastic_black")
    # пластина целика с диоптром у заднего края
    from lib import boolean
    plate_pts = fillet([(xa + 0.5, 44.0), (xa + 4.5, 44.0), (xa + 4.5, 66.0), (xa + 0.5, 66.0)], [1.0] * 4, seg=3)
    plate = rounded_prism("Rear_sight_plate", plate_pts, hy + 1.0, hy + 17.0, 0.8, coll, "Plastic_black")
    hole = cyl("_peep", xa - 2.0, xa + 7.0, 1.6, coll, None, seg=24, cy=hy + 9.0, cz=58.0)
    boolean(plate, hole)
    # кремовый колпачок индикатора (ось X, смотрит назад к глазу) и тонкое перо
    ind = lathe("Rear_sight_indicator", [(0.0, 0.0), (0.0, 6.4), (0.6, 7.6), (12.0, 7.6), (12.6, 6.6), (12.8, 0.0)], coll,
                "Indicator_cream", seg=48)
    ind.data.transform(Matrix.Translation(v(px_x(755) - 1.0, hy + 8.0, px_z(743, 354.5))))
    blade = cyl("Rear_sight_blade", 58.0, px_z(760, 305), 1.1, coll, "Plastic_black", seg=16, cy=px_x(760), cz=hy + 12.0,
                axis="Z")
    from lib import join
    leaf_o = join([body, plate, blade], "Rear_sight_leaf")
    # ось — у заднего края основания: при складывании назад всё «перо» поднимается над основанием, не задевая его
    set_origin(leaf_o, (xa, hy + 6.0, hz))
    ind.parent = None
    return [base, leaf_o, ind]


def sling_loop(coll):
    """Передняя петля ремня слева на накладке (снимок: 560…580 × 357…407)."""
    xa, xb = px_x(580), px_x(560)
    za, zb = px_z(570, 407), px_z(570, 357)
    pts = fillet([(xa, za), (xb, za), (xb, zb), (xa, zb)], [3.0] * 4, seg=4)
    blk = rounded_prism("Sling_loop_base", pts, D.SADDLE_LEFT - 2.0, D.SADDLE_LEFT + 4.0, 1.2, coll, "Paint_olive_cast")
    # проволочная скоба: полукольцо в плоскости XZ, наружу
    me = bpy.data.meshes.new("Sling_loop_wire")
    bm = bmesh.new()
    rw, rr = 1.6, (zb - za) / 2 - 2.0
    cz = (za + zb) / 2
    cx = (xa + xb) / 2
    segs, ring_n = 24, 12
    rings = []
    for i in range(segs + 1):
        t = -math.pi / 2 + math.pi * i / segs
        cpos = Vector((cx, D.SADDLE_LEFT + 3.0 + 6.0 * math.cos(t), cz + rr * math.sin(t)))
        tang = Vector((0, -math.sin(t), math.cos(t))).normalized()
        nrm = Vector((1, 0, 0))
        bin_ = tang.cross(nrm)
        rings.append([bm.verts.new((cpos + (nrm * math.cos(2 * math.pi * k / ring_n) + bin_ * math.sin(2 * math.pi * k / ring_n)) * rw) * MM)
                      for k in range(ring_n)])
    for a, b in zip(rings, rings[1:]):
        for k in range(ring_n):
            j = (k + 1) % ring_n
            bm.faces.new((a[k], a[j], b[j], b[k]))
    bm.faces.new(list(reversed(rings[0]))); bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    wire = _obj("Sling_loop_wire", me, coll, "Steel_black")
    return [blk, wire]


def side_rib(coll):
    """Продольное ребро по низу левого бока накладки (снимок: y 455…465 на x 380…760)."""
    za, zb = px_z(560, 465), px_z(560, 455)
    xa, xb = SADDLE_REAR_X + 3.0, px_x(380)
    pts = fillet([(xa, za), (xb, za), (xb, zb), (xa, zb)], [2.4] * 4, seg=4)
    return rounded_prism("Saddle_side_rib", pts, D.SADDLE_LEFT - 1.0, D.SADDLE_LEFT + 2.2, 0.9, coll, "Paint_olive_cast")


def build(ctx):
    C = ctx["coll"]["Saddle"]
    S = ctx["coll"]["Sights"]
    out = [saddle(C), side_rib(C)]
    out += lids(C)
    out += right_flange(C)
    out += front_right_plate(C)
    out += mount_plate(C)
    dc = dust_cover(C)
    fs = front_sight(S)
    rs = rear_sight(S)
    sl = sling_loop(C)
    return {"dust_cover": dc[1], "front_sight": fs[1], "rear_sight": rs[1], "rear_indicator": rs[2]}
