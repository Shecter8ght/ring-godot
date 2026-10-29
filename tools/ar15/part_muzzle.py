# AR-15: дульный тормоз (три камеры с крупными боковыми окнами, передняя стенка с отверстием), контргайка у заплечика,
# храповая муфта-фиксатор под быстросъёмный глушитель и сам глушитель (рёбра сзади, конусные перегородки внутри,
# посадочный конус под тормоз, подпружиненный рычаг-собачка на муфту). Канал насквозь, видно с обоих торцов.
# Раскладка по X (мм): контргайка 278–282, шейка тормоза под муфтой 282–290, посадочный конус 290–296,
# окна 296–340; глушитель от 290 (задний торец) до 290 + SUPPRESSOR_LEN.
import math
import bpy
import lib as _lib
from lib import (MM, THREAD_X, BRAKE_X, SUPPRESSOR_R, SUPPRESSOR_LEN, fillet, prism_xz, prism_yz, box, cyl, lathe,
                 boolean, finish, join, auto_sharp, apply_transform, set_parent, set_origin)

NUT_X = (THREAD_X[0], 281.95)         # контргайка на резьбе ствола (зазор 0.05 до тормоза)
COLLAR_X = (282.05, 289.95)           # храповая муфта-фиксатор (зазоры 0.05 до гайки и посадочного конуса)
SEAT_X = (290.0, 296.0)               # посадочный конус глушителя
BRAKE_R = 12.7                        # тормоз Ø25.4
BORE_R = 3.4                          # канал тормоза и перегородок Ø6.8
THREAD_R = 6.35                       # 1/2-28
CHAMBERS = ((298.5, 308.5), (311.5, 321.5), (324.5, 334.0))
SUP_REAR = SEAT_X[0] + 0.3            # задний торец глушителя — зазор-стык 0.3 мм с муфтой
SUP_FRONT = SUP_REAR + SUPPRESSOR_LEN
SUP_BORE_R = 4.2                      # канал глушителя Ø8.4
LATCH_PIVOT = (300.0, 18.4)           # ось рычага-собачки (x, z), вдоль Y
COLLAR_BAND_R = 13.1                  # поясок муфты с пазами храповика
RATCHET_N = 18                        # пазов по окружности; паз 0 — сверху, под зубом собачки
RATCHET_ROOT = 12.3                   # дно паза


def _star(r_out, r_in, n, phase=0.0, sub=2):
    """Зубчатое сечение (y, z) с n зубьями: трапеции, вершина r_out, впадина r_in."""
    pts = []
    for k in range(n):
        a0 = 2 * math.pi * k / n + phase
        da = 2 * math.pi / n
        for t, r in ((0.0, r_in), (0.18, r_out), (0.50, r_out), (0.68, r_in)):
            a = a0 + da * t
            pts.append((r * math.cos(a), r * math.sin(a)))
    return pts


def _ring_x(name, x0, x1, r0, r1, coll, mat=None, seg=48):
    """Кольцо вдоль X: внутренний r0, наружный r1."""
    return lathe(name, [(x0, r0), (x0, r1), (x1, r1), (x1, r0)], coll, mat, seg=seg)


def _text_cutter(text, size, depth, coll, wrap_r=None, bold=0.02):
    """Резак гравировки: заливка текста в плоскости, сварка вершин, выдавливание от −depth до +1 мм (замкнутая сетка).
    wrap_r — изгиб по цилиндру (локальная Y — вдоль окружности, Z — по нормали), чтобы глубина везде была одна."""
    import bmesh
    cu = bpy.data.curves.new("_eng", "FONT")
    cu.body = text
    cu.size = size * MM
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = 0.0
    cu.fill_mode = "BOTH"
    cu.offset = size * bold * MM
    cu.resolution_u = 5
    tmp = bpy.data.objects.new("_eng", cu)
    coll.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.curves.remove(cu)
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    for vv in bm.verts:
        vv.co.z = -depth * MM
    r = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    for vv in [e for e in r["geom"] if isinstance(e, bmesh.types.BMVert)]:
        vv.co.z += (depth + 1.0) * MM
    if wrap_r:
        R = wrap_r * MM
        for vv in bm.verts:
            y = vv.co.y
            vv.co.z -= R - math.sqrt(max(R * R - y * y, 0.0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new("_engm", me)
    coll.objects.link(ob)
    return ob


def engrave(target, text, size, center, normal, up, depth, coll, wrap_r=None):
    """Гравировка: текст в плоскости ⟂ normal, «вверх» — up, строка идёт вдоль up × normal; center — точка на поверхности (мм)."""
    from mathutils import Matrix, Vector
    cut = _text_cutter(text, size, depth, coll, wrap_r)
    n = Vector(normal).normalized(); u = Vector(up).normalized(); r = u.cross(n)
    m = Matrix((r, u, n)).transposed().to_4x4()
    m.translation = Vector(center) * MM
    cut.data.transform(m)              # резак в мировых координатах: модификатор сам учтёт положение детали
    boolean(target, cut)


def build(ctx):
    M = ctx["coll"]["Muzzle"]
    S = ctx["coll"]["Suppressor"]
    out = {}
    out.update(brake(M))
    out.update(suppressor(S))
    return out


def brake(M):
    o = {}
    # --- контргайка: шестигранник 3/4″ под ключ, фаски по углам ---
    hexa = [(9.5 / math.cos(math.pi / 6) * math.cos(math.radians(30 + 60 * k)),
             9.5 / math.cos(math.pi / 6) * math.sin(math.radians(30 + 60 * k))) for k in range(6)]
    nut = prism_yz("Muzzle_jam_nut", hexa, NUT_X[0], NUT_X[1], M, "Steel_black")
    # фаска углов шестигранника — пересечение с двойным конусом
    cone = lathe("nut_cone", [(NUT_X[0] - 0.01, 0.0), (NUT_X[0] - 0.01, 9.7), (NUT_X[0] + 1.0, 10.9), (NUT_X[1] - 1.0, 10.9),
                              (NUT_X[1] + 0.01, 9.7), (NUT_X[1] + 0.01, 0.0)], M, None, seg=64)
    boolean(nut, cone, "INTERSECT")
    boolean(nut, cyl("cut_nut_bore", NUT_X[0] - 1, NUT_X[1] + 1, THREAD_R, M, seg=48))
    finish(nut, w=0.2, seg=2, angle=35)
    o["jam_nut"] = nut

    # --- корпус тормоза ---
    x0, x1 = 282.0, BRAKE_X[1]
    prof = [(x0, 0.0), (x0, 9.3), (x0 + 0.5, 9.8), (SEAT_X[0], 9.8), (SEAT_X[0], 11.5), (SEAT_X[1], BRAKE_R),
            (x1 - 1.2, BRAKE_R), (x1, BRAKE_R - 1.2), (x1, 0.0)]
    br = lathe("Muzzle_brake", prof, M, "Steel_black", seg=96)
    boolean(br, cyl("cut_brake_bore", THREAD_X[1] - 0.5, x1 + 1, BORE_R, M, seg=40))
    # три камеры: полость внутри и сквозные боковые окна
    for i, (c0, c1) in enumerate(CHAMBERS):
        boolean(br, cyl(f"cut_chamber{i}", c0, c1, 8.6, M, seg=64))
        win = prism_xz(f"cut_port{i}", fillet([(c0, -7.3), (c1, -7.3), (c1, 7.3), (c0, 7.3)], 3.8, 6), -20, 20, M)
        boolean(br, win)
        # верхний компенсаторный паз
        top = prism_xz(f"cut_top{i}", fillet([(c0 + 2.6, -2.0), (c1 - 2.6, -2.0), (c1 - 2.6, 2.0), (c0 + 2.6, 2.0)], 1.9, 5), -2.0, 2.0, M)
        top.rotation_euler = (math.radians(90), 0, 0)
        apply_transform(top)
        top.location.z = 11.0 * MM
        apply_transform(top)
        boolean(br, top)
    # «корона» на переднем торце: зенковка вокруг канала и четыре прорези
    boolean(br, lathe("cut_crown", [(x1 - 1.6, 0.0), (x1 - 1.6, BORE_R + 0.6), (x1 + 0.1, BORE_R + 2.6), (x1 + 0.1, 0.0)], M, None, seg=48))
    for k in range(4):
        c = box(f"cut_crown_slot{k}", x1 - 1.0, x1 + 0.6, -1.0, 1.0, BORE_R + 3.0, BRAKE_R - 2.5, M)
        c.rotation_euler = (math.radians(45 + 90 * k), 0, 0)
        apply_transform(c)
        boolean(br, c)
    # резьба внутри сзади (на ствол) и канал
    boolean(br, cyl("cut_brake_thread", x0 - 1, THREAD_X[1] + 0.2, THREAD_R, M, seg=48))
    for k in range(int((THREAD_X[1] - x0) / 1.0)):
        xx = x0 + 0.9 + k * 0.907                         # шаг 28 витков на дюйм
        if xx > THREAD_X[1] - 0.6:
            break
        boolean(br, lathe("cut_thr", [(xx - 0.3, THREAD_R - 0.1), (xx, THREAD_R + 0.45), (xx + 0.3, THREAD_R - 0.1)], M, None, seg=48))
    # лыски под ключ сверху и снизу вдоль всего корпуса с окнами
    for s in (-1, 1):
        z0, z1 = (11.6, 20.0) if s > 0 else (-20.0, -11.6)
        boolean(br, box(f"cut_flat{s}", SEAT_X[1] + 0.8, x1 - 1.6, -20, 20, z0, z1, M))
    finish(br, w=0.35, seg=2, angle=35)
    # калибр на нижней лыске (видно снизу) — только по флагу, иначе место остаётся ровным под текстуру
    if getattr(_lib, "MARKINGS_GEOMETRY", False):
        engrave(br, "5,56", 2.4, ((CHAMBERS[1][0] + CHAMBERS[1][1]) / 2, 0.0, -11.6), (0, 0, -1), (-1, 0, 0), 0.12, M)
    o["brake"] = br

    # --- храповая муфта: рифлёная снаружи (под пальцы), спереди гладкий поясок с пазами храповика по окружности,
    #     в паз падает зуб собачки глушителя ---
    col = prism_yz("Muzzle_lock_collar", _star(13.5, 12.85, 40), COLLAR_X[0], COLLAR_X[1] - 2.4, M, "Steel_black")
    band = _ring_x("collar_band", COLLAR_X[1] - 2.8, COLLAR_X[1], 9.0, COLLAR_BAND_R, M, "Steel_black", seg=72)
    boolean(col, band, "UNION")
    boolean(col, cyl("cut_collar_bore", COLLAR_X[0] - 1, COLLAR_X[1] + 1, 9.85, M, seg=72))
    notches = []
    for k in range(RATCHET_N):
        c = prism_yz(f"cut_ratchet{k}", [(-1.05, COLLAR_BAND_R + 0.6), (1.05, COLLAR_BAND_R + 0.6), (0.35, RATCHET_ROOT),
                                         (-0.35, RATCHET_ROOT)], COLLAR_X[1] - 2.2, COLLAR_X[1] + 0.5, M)
        c.rotation_euler = (2 * math.pi * k / RATCHET_N, 0, 0)
        apply_transform(c)
        notches.append(c)
    boolean(col, join(notches, "cut_ratchet"))
    # задняя фаска
    boolean(col, lathe("cut_collar_ch", [(COLLAR_X[0] - 0.1, 12.3), (COLLAR_X[0] + 1.0, 13.7), (COLLAR_X[0] - 0.1, 13.7)], M, None, seg=72))
    finish(col, w=0.15, seg=2, angle=35)
    set_origin(col, ((COLLAR_X[0] + COLLAR_X[1]) / 2, 0.0, 0.0))
    o["collar"] = col
    return o


def suppressor(S):
    """Глушитель — самостоятельный предмет: корень Suppressor_body (начало — центр посадочного торца на оси),
    перегородки, собачка и ось — его дети. Построен в положении «установлен на тормоз»."""
    o = {}
    R = SUPPRESSOR_R
    x0, x1 = SUP_REAR, SUP_FRONT
    cap0 = x1 - 12.0                      # передняя крышка
    prof = [(x0, 0.0), (x0, R - 2.0), (x0 + 2.0, R), (x1 - 13.0, R), (x1 - 12.4, R - 0.9), (cap0 + 0.6, R - 0.9),
            (cap0 + 1.2, R - 0.7), (x1 - 1.6, R - 0.7), (x1, R - 2.4), (x1, 0.0)]
    body = lathe("Suppressor_body", prof, S, "Steel_black", seg=120)
    # внутренняя полость: посадочный конус, камера тормоза, полость перегородок, передний канал
    cav = lathe("cut_sup_cav", [(x0 - 0.5, 0.0), (x0 - 0.5, 11.75), (SEAT_X[1] + 0.05, 12.95), (SEAT_X[1] + 0.05, 14.0),
                                (BRAKE_X[1] + 3.0, 14.0), (BRAKE_X[1] + 3.0, 17.5), (x1 - 8.0, 17.5), (x1 - 8.0, SUP_BORE_R),
                                (x1 + 0.5, SUP_BORE_R), (x1 + 0.5, 0.0)], S, None, seg=120)
    boolean(body, cav)
    # рифлёный поясок под пальцы у посадки (быстросъём крутят рукой): 48 продольных бороздок
    ridges = []
    for k in range(48):
        g = box(f"cut_grip{k}", x0 + 2.8, x0 + 7.6, -0.42, 0.42, R - 0.45, R + 1.0, S)
        g.rotation_euler = (2 * math.pi * k / 48, 0, 0)
        apply_transform(g)
        ridges.append(g)
    boolean(body, join(ridges, "cut_grip"))
    # кольцевые канавки: за пояском, перед рёбрами и за ними
    for xa, w, d in ((x0 + 8.6, 0.9, 0.7), (x0 + 49.2, 1.4, 0.8), (x0 + 52.4, 0.8, 0.5)):
        boolean(body, lathe("cut_ring", [(xa, R - d), (xa, R + 1), (xa + w, R + 1), (xa + w, R - d)], S, None, seg=120))
    # продольные рёбра сзади: 16 канавок с круглыми концами
    cuts = []
    for k in range(16):
        g = prism_xz(f"cut_flute{k}", fillet([(x0 + 11.0, R - 1.6), (x0 + 46.5, R - 1.6), (x0 + 46.5, R + 2), (x0 + 11.0, R + 2)],
                                             [1.4, 1.4, 0, 0], 4), -1.6, 1.6, S)
        g.rotation_euler = (2 * math.pi * k / 16 + math.pi / 16, 0, 0)
        apply_transform(g)
        cuts.append(g)
    boolean(body, join(cuts, "cut_flutes"))
    # передняя крышка: две лыски под ключ по бокам, кольцевая проточка, «корона» из 8 пазов, отверстия под рожковый ключ
    for sgn in (-1, 1):
        y0, y1 = (R - 2.4, R + 2) if sgn > 0 else (-R - 2, -R + 2.4)
        boolean(body, box(f"cut_cap_flat{sgn}", cap0 + 2.0, x1 - 2.4, y0, y1, -8.5, 8.5, S))
    boolean(body, lathe("cut_front_groove", [(x1 - 0.8, 8.4), (x1 - 0.8, 10.2), (x1 + 0.2, 10.2), (x1 + 0.2, 8.4)], S, None, seg=96))
    crown = []
    for k in range(8):
        c = box(f"cut_crown{k}", x1 - 0.9, x1 + 0.5, -0.8, 0.8, SUP_BORE_R + 1.7, 8.0, S)
        c.rotation_euler = (2 * math.pi * k / 8 + math.pi / 8, 0, 0)
        apply_transform(c)
        crown.append(c)
    boolean(body, join(crown, "cut_crown"))
    boolean(body, lathe("cut_bore_ch", [(x1 - 1.3, 0.0), (x1 - 1.3, SUP_BORE_R - 0.1), (x1 + 0.1, SUP_BORE_R + 1.2), (x1 + 0.1, 0.0)],
                        S, None, seg=64))
    for sgn in (-1, 1):
        boolean(body, cyl(f"cut_spanner{sgn}", x1 - 2.2, x1 + 1, 1.2, S, seg=20, cy=13.6 * sgn, cz=0.0))
    # паз под рычаг-собачку сверху сзади и ось рычага
    boolean(body, box("cut_latch_slot", x0 - 1.0, x0 + 20.0, -2.7, 2.7, R - 3.6, R + 2, S))
    boolean(body, box("cut_latch_well", LATCH_PIVOT[0] + 1.5, x0 + 20.0, -2.7, 2.7, R - 5.0, R - 3.4, S))
    boolean(body, cyl("cut_latch_pin", -R, R, 1.0, S, seg=16, cy=LATCH_PIVOT[0], cz=LATCH_PIVOT[1], axis="Y"))
    finish(body, w=0.3, seg=2, angle=30)
    set_origin(body, (x0, 0.0, 0.0))
    # гравировка вымышленной марки, калибра и номера — справа сверху вдоль трубы (видна на правом виде)
    ang = math.radians(35.0)
    n = (0.0, -math.sin(ang), math.cos(ang))
    u = (0.0, math.cos(ang), math.sin(ang))

    def on(xc, off):
        return (xc, R * n[1] - off * u[1], R * n[2] - off * u[2])
    # место под надписи (марка, калибр, номер) — гладкая труба справа сверху, x0+80…x0+125; надписи наносятся
    # на этапе текстур, в геометрию — только по флагу lib.MARKINGS_GEOMETRY
    if getattr(_lib, "MARKINGS_GEOMETRY", False):
        engrave(body, "ГРАНЬ", 5.6, on(x0 + 92.0, -1.6), n, u, 0.18, S, wrap_r=R)
        engrave(body, "5,56", 3.2, on(x0 + 117.0, -1.3), n, u, 0.15, S, wrap_r=R)
        engrave(body, "№ 31-0458", 2.4, on(x0 + 95.0, 3.7), n, u, 0.13, S, wrap_r=R)
        from lib import renormal
        renormal(body)
    o["body"] = body
    # --- конусные перегородки ---
    pitch = 13.0
    xb = BRAKE_X[1] + 4.0
    k = 0
    while xb + pitch <= x1 - 8.0 + 0.01:
        prof = [(xb, 17.45), (xb + pitch - 0.05, 17.45), (xb + pitch - 0.05, 15.6), (xb + 3.4, SUP_BORE_R + 0.1),
                (xb + 1.8, SUP_BORE_R + 0.1), (xb + 11.6, 16.4), (xb, 16.4)]
        b = lathe(f"Suppressor_baffle{k}", prof, S, "Steel_black", seg=72)
        # косой срез «K» у кромки канала — отсекает струю
        boolean(b, box(f"cut_baffle_notch{k}", xb + 1.0, xb + 4.6, -3.0, 3.0, SUP_BORE_R - 0.5, SUP_BORE_R + 3.0, S))
        finish(b, w=0.15, seg=2, angle=35)
        set_parent(b, body)
        o[f"baffle{k}"] = b
        xb += pitch
        k += 1
    # --- рычаг-собачка: хвост тянется назад над муфтой, узкий зуб падает в паз храповика (паз 0 — сверху) ---
    px, pz = LATCH_PIVOT
    lev = prism_xz("Suppressor_latch", fillet([(x0 - 0.4, R - 3.2), (px + 9.0, R - 3.2), (x0 + 19.0, R - 2.0), (x0 + 19.0, R + 0.9),
                                               (px + 2.0, R + 0.9), (x0 + 2.0, R - 0.4), (x0 - 3.4, R - 0.7), (x0 - 3.4, 15.0),
                                               (x0 - 0.4, 15.0)], [0.6, 1.5, 1.2, 1.2, 2.0, 1.5, 1.0, 0.8, 0.6], 3),
                   -2.4, 2.4, S, "Steel_black")
    # узкий зуб: клин в паз храповика
    tooth = prism_yz("latch_tooth", [(-0.6, 15.2), (0.6, 15.2), (0.25, RATCHET_ROOT + 0.25), (-0.25, RATCHET_ROOT + 0.25)],
                     x0 - 2.3, x0 - 0.9, S, "Steel_black")
    boolean(lev, tooth, "UNION")
    boolean(lev, cyl("cut_lev_pin", -5, 5, 1.05, S, seg=16, cy=px, cz=pz, axis="Y"))
    for j in range(6):
        xx = x0 + 10.4 + j * 1.5
        boolean(lev, box(f"cut_lev_ser{j}", xx - 0.32, xx + 0.32, -3, 3, R + 0.45, R + 2, S))
    finish(lev, w=0.2, seg=2, angle=35)
    set_origin(lev, (px, 0.0, pz))
    set_parent(lev, body)
    o["latch"] = lev
    pin = cyl("Suppressor_latch_pin", -2.65, 2.65, 1.0, S, "Steel_bare", seg=16, cy=px, cz=pz, axis="Y", ch=0.2)
    set_parent(pin, body)
    o["latch_pin"] = pin
    return o
