# AR-15: дульный тормоз (три камеры с крупными боковыми окнами, передняя стенка с отверстием), контргайка у заплечика,
# храповая муфта-фиксатор под быстросъёмный глушитель и сам глушитель (рёбра сзади, конусные перегородки внутри,
# посадочный конус под тормоз, подпружиненный рычаг-собачка на муфту). Канал насквозь, видно с обоих торцов.
# Раскладка по X (мм): контргайка 278–282, шейка тормоза под муфтой 282–290, посадочный конус 290–296,
# окна 296–340; глушитель от 290 (задний торец) до 290 + SUPPRESSOR_LEN.
import math
import bpy
from lib import (MM, THREAD_X, BRAKE_X, SUPPRESSOR_R, SUPPRESSOR_LEN, fillet, prism_xz, prism_yz, box, cyl, lathe,
                 boolean, finish, join, auto_sharp, apply_transform, set_parent, set_origin)

NUT_X = (THREAD_X[0], 282.0)          # контргайка на резьбе ствола
COLLAR_X = (282.0, 290.0)             # храповая муфта-фиксатор
SEAT_X = (290.0, 296.0)               # посадочный конус глушителя
BRAKE_R = 12.7                        # тормоз Ø25.4
BORE_R = 3.4                          # канал тормоза и перегородок Ø6.8
THREAD_R = 6.35                       # 1/2-28
CHAMBERS = ((298.5, 308.5), (311.5, 321.5), (324.5, 334.0))
SUP_REAR = SEAT_X[0]                  # задний торец глушителя прилегает к муфте
SUP_FRONT = SUP_REAR + SUPPRESSOR_LEN
SUP_BORE_R = 4.2                      # канал глушителя Ø8.4
LATCH_PIVOT = (300.0, 18.4)           # ось рычага-собачки (x, z), вдоль Y


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
    x0, x1 = COLLAR_X[0], BRAKE_X[1]
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
    finish(br, w=0.25, seg=2, angle=35)
    o["brake"] = br

    # --- храповая муфта: рифлёная снаружи (под пальцы), зубья храповика на переднем торце ---
    col = prism_yz("Muzzle_lock_collar", _star(13.5, 12.7, 36), COLLAR_X[0], COLLAR_X[1], M, "Steel_black")
    boolean(col, cyl("cut_collar_bore", COLLAR_X[0] - 1, COLLAR_X[1] + 1, 9.85, M, seg=64))
    # передняя часть — гладкий поясок с косыми зубьями храповика по торцу
    band = _ring_x("collar_band", COLLAR_X[1] - 2.0, COLLAR_X[1] + 0.01, 9.0, 14.5, M)
    boolean(col, band)
    ring = _ring_x("collar_ring", COLLAR_X[1] - 2.2, COLLAR_X[1], 9.85, 13.0, M, "Steel_black", seg=64)
    boolean(col, ring, "UNION")
    for k in range(18):
        a = 2 * math.pi * k / 18
        t = prism_xz(f"collar_tooth{k}", [(COLLAR_X[1] - 2.2, 10.6), (COLLAR_X[1] - 0.2, 10.6), (COLLAR_X[1] - 2.2, 13.0)], -1.1, 1.1, M, "Steel_black")
        t.rotation_euler = (a, 0, 0)
        apply_transform(t)
        boolean(col, t, "UNION")
    # задняя фаска
    boolean(col, lathe("cut_collar_ch", [(COLLAR_X[0] - 0.1, 12.2), (COLLAR_X[0] + 1.0, 13.6), (COLLAR_X[0] - 0.1, 13.6)], M, None, seg=64))
    finish(col, w=0.15, seg=2, angle=35)
    set_origin(col, ((COLLAR_X[0] + COLLAR_X[1]) / 2, 0.0, 0.0))
    o["collar"] = col
    return o


def suppressor(S):
    o = {}
    R = SUPPRESSOR_R
    x0, x1 = SUP_REAR, SUP_FRONT
    prof = [(x0, 0.0), (x0, R - 2.0), (x0 + 2.0, R), (x0 + 6.0, R), (x0 + 6.0, R - 0.6), (x0 + 6.8, R - 0.6), (x0 + 6.8, R),
            (x0 + 49.0, R), (x0 + 49.0, R - 0.8), (x0 + 51.0, R - 0.8), (x0 + 51.0, R),
            (x1 - 9.0, R), (x1 - 9.0, R - 0.9), (x1 - 7.5, R - 0.9), (x1 - 7.5, R - 1.4), (x1 - 1.2, R - 1.4), (x1, R - 2.6), (x1, 0.0)]
    body = lathe("Suppressor_body", prof, S, "Steel_black", seg=96)
    # внутренняя полость: посадочный конус, камера тормоза, полость перегородок, передний канал
    cav = lathe("cut_sup_cav", [(x0 - 0.5, 0.0), (x0 - 0.5, 11.6), (SEAT_X[1] + 0.05, 12.8), (SEAT_X[1] + 0.05, 14.0),
                                (BRAKE_X[1] + 3.0, 14.0), (BRAKE_X[1] + 3.0, 17.5), (x1 - 8.0, 17.5), (x1 - 8.0, SUP_BORE_R),
                                (x1 + 0.5, SUP_BORE_R), (x1 + 0.5, 0.0)], S, None, seg=96)
    boolean(body, cav)
    # продольные рёбра сзади: 16 канавок с круглыми концами
    cuts = []
    for k in range(16):
        g = prism_xz(f"cut_flute{k}", fillet([(x0 + 9.0, R - 1.6), (x0 + 46.0, R - 1.6), (x0 + 46.0, R + 2), (x0 + 9.0, R + 2)],
                                             [1.4, 1.4, 0, 0], 4), -1.6, 1.6, S)
        g.rotation_euler = (2 * math.pi * k / 16 + math.pi / 16, 0, 0)
        apply_transform(g)
        cuts.append(g)
    boolean(body, join(cuts, "cut_flutes"))
    # передний торец: кольцевая проточка и два отверстия под ключ
    boolean(body, lathe("cut_front_groove", [(x1 - 0.8, 8.4), (x1 - 0.8, 10.2), (x1 + 0.2, 10.2), (x1 + 0.2, 8.4)], S, None, seg=64))
    for s in (-1, 1):
        boolean(body, cyl(f"cut_spanner{s}", x1 - 2.2, x1 + 1, 1.2, S, seg=16, cy=13.5 * s, cz=0.0))
    # паз под рычаг-собачку сверху сзади
    boolean(body, box("cut_latch_slot", x0 - 1.0, x0 + 20.0, -2.7, 2.7, R - 3.6, R + 2, S))
    boolean(body, cyl("cut_latch_pin", -R, R, 1.0, S, seg=16, cy=LATCH_PIVOT[0], cz=LATCH_PIVOT[1], axis="Y"))
    finish(body, w=0.3, seg=2, angle=30)
    set_origin(body, (x0, 0.0, 0.0))
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
        auto_sharp(b, 35)
        set_parent(b, body)
        o[f"baffle{k}"] = b
        xb += pitch
        k += 1
    # --- рычаг-собачка: хвост с зубом заходит назад за торец на зубья муфты ---
    px, pz = LATCH_PIVOT
    lev = prism_xz("Suppressor_latch", fillet([(x0 - 2.6, 13.75), (x0 - 0.6, 13.75), (x0 + 0.6, R - 3.2), (px + 9.0, R - 3.2),
                                               (x0 + 19.0, R - 2.0), (x0 + 19.0, R + 0.9), (px + 2.0, R + 0.9), (x0 + 2.0, R - 0.4),
                                               (x0 - 2.6, R - 0.6)], [0.4, 0.6, 1.5, 1.5, 1.2, 1.2, 2.0, 1.5, 1.0], 3),
                   -2.4, 2.4, S, "Steel_black")
    boolean(lev, cyl("cut_lev_pin", -5, 5, 1.05, S, seg=16, cy=px, cz=pz, axis="Y"))
    for j in range(5):
        xx = x0 + 11.0 + j * 1.6
        boolean(lev, box(f"cut_lev_ser{j}", xx - 0.35, xx + 0.35, -3, 3, R + 0.45, R + 2, S))
    finish(lev, w=0.2, seg=2, angle=35)
    set_origin(lev, (px, 0.0, pz))
    set_parent(lev, body)
    o["latch"] = lev
    pin = cyl("Suppressor_latch_pin", -2.65, 2.65, 1.0, S, "Steel_bare", seg=16, cy=px, cz=pz, axis="Y", ch=0.2)
    set_parent(pin, body)
    o["latch_pin"] = pin
    return o
