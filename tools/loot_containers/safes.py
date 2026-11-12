"""Сейфы: напольный офисный и настенный встраиваемый (ячейка)."""
import math

import bmesh
from mathutils import Matrix

import lc
from lc import L, V, part, shell_part, cyl, plug

R = lc.R if hasattr(lc, "R") else None


def _rot_z(ob, deg):
    ob.rotation_euler = (0, 0, math.radians(deg))


def lathe_y(bm, prof, c, segs=32):
    """Тело вращения вокруг оси, идущей наружу двери (−Y): h — вылет от плоскости c."""
    lc.lathe(bm, prof, segs=segs, origin=c, axis=(0, -1, 0))


# ================================================================ сейф напольный офисный

def floor_safe(coll, m, at, open_: bool):
    """Сейф напольный офисный 500 × 700 × 450: сварной корпус (лист 3 мм) с рамой-обвязкой проёма, дверца в проёме
    (лоток 3 мм с внутренним листом, ригели в торце входят в карманы рамы), две наружные петли-штыря, лимб кодового
    замка с рисками, штурвал на три спицы; внутри полка и запираемый верхний отсек (трейзер) со своей дверцей."""
    r = L.root("СН_сейф_напольный" + ("_открыт" if open_ else ""), coll, at)
    W, D, H, z0 = 0.50, 0.45, 0.70, 0.012
    hw, yf = W / 2, -D / 2
    # корпус: оболочка без передней грани
    body = shell_part("СН_корпус", coll, [m["steel_a"]], r, (W, D, H - z0), 0.007, (0, 0, (H + z0) / 2), "-y", 0.003)
    # рама проёма: 4 обвязки шириной 24 мм, глубиной 30 мм; в боковых — карманы под ригели
    bw = 0.024
    fb = bmesh.new()
    L.bm_box(fb, (-hw + 0.003, yf, z0), (hw - 0.003, yf + 0.03, z0 + bw))
    L.bm_box(fb, (-hw + 0.003, yf, H - bw), (hw - 0.003, yf + 0.03, H - 0.003))
    z_lo, z_hi = z0 + bw, H - bw
    rig_z = [0.20, 0.34, 0.48]  # ригели на стороне замка (справа)
    ded_z = [0.22, 0.46]          # штыри-«мёртвые» ригели на стороне петель (слева)
    for s, zs in ((1, rig_z), (-1, ded_z)):
        xo, xm, xi = s * (hw - 0.003), s * (hw - 0.014), s * (hw - bw)
        # наружный слой обвязки — сплошной, внутренний — сегментами между карманами (карманы глубиной 10 мм)
        L.bm_box(fb, (min(xo, xm), yf, z_lo), (max(xo, xm), yf + 0.03, z_hi))
        edges = [z_lo] + sum([[z - 0.011, z + 0.011] for z in zs], []) + [z_hi]
        for k in range(0, len(edges), 2):
            L.bm_box(fb, (min(xm, xi), yf, edges[k]), (max(xm, xi), yf + 0.03, edges[k + 1]))
    lc.obj(fb, "СН_рама_проёма", coll, [m["steel_a"]], r, bevel=0.0012, segs=2, smooth=45)
    # опоры (резиновые ножки) и задняя ребристая накладка
    fm = bmesh.new()
    for x in (-hw + 0.04, hw - 0.04):
        for y in (-D / 2 + 0.04, D / 2 - 0.04):
            cyl(fm, (x, y, 0.0), (x, y, z0 + 0.001), 0.018, segs=20, r1=0.016)
    lc.obj(fm, "СН_ножки", coll, [m["rubber"]], r, smooth=50)
    # полка
    sb = bmesh.new()
    lc.rbox(sb, (W - 0.012, D - 0.07, 0.008), 0.003, (0, 0.012, 0.31), seg=2)
    lc.obj(sb, "СН_полка", coll, [m["steel_a"]], r, smooth=50)
    # трейзер: дно, потолок отсека (между ними 12 см) и дверца
    zt0, zt1 = 0.550, 0.672
    tb = bmesh.new()
    lc.rbox(tb, (W - 0.012, D - 0.12, 0.008), 0.0025, (0, 0.0, zt0 - 0.004), seg=2)
    lc.rbox(tb, (W - 0.012, D - 0.12, 0.004), 0.0015, (0, 0.0, zt1 + 0.002), seg=2)
    lc.obj(tb, "СН_трейзер_отсек", coll, [m["steel_c"]], r, smooth=50)
    # --- дверца основная: лоток, внутренний лист, механизм ригелей
    dw0, dw1 = -hw + bw + 0.003, hw - bw - 0.003   # x −0.223…0.223
    dz0, dz1 = z_lo + 0.003, z_hi - 0.003
    dpiv = (dw0 - 0.007, yf - 0.0085, 0.0)           # ось петель-штырей: вертикаль
    dcx, dcz = (dw0 + dw1) / 2, (dz0 + dz1) / 2
    door = shell_part("СН_дверца", coll, [m["steel_b"]], r, (dw1 - dw0, 0.040, dz1 - dz0), 0.004,
                      (dcx, yf + 0.020, dcz), "+y", 0.003, piv=dpiv, mover=True)
    # внутренний лист и механизм
    ib = bmesh.new()
    lc.rbox(ib, (dw1 - dw0 - 0.020, 0.004, dz1 - dz0 - 0.020), 0.002, (dcx, yf + 0.0285, dcz), seg=2)
    # корпус замка (кодовый) и тяговая планка
    L.bm_box(ib, (0.02, yf + 0.0305, 0.40), (0.15, yf + 0.0305 + 0.016, 0.57))
    L.bm_box(ib, (dw1 - 0.075, yf + 0.0305, dz0 + 0.04), (dw1 - 0.062, yf + 0.0305 + 0.006, dz1 - 0.04))
    for z in rig_z:
        L.bm_box(ib, (dw1 - 0.075, yf + 0.0305, z - 0.017), (dw1 - 0.015, yf + 0.0305 + 0.008, z + 0.017))
    for z in ded_z:
        L.bm_box(ib, (dw0 + 0.012, yf + 0.0305, z - 0.017), (dw0 + 0.06, yf + 0.0305 + 0.008, z + 0.017))
    ib_ob = part(ib, "СН_дверца_механизм", coll, [m["steel_raw"]], door, dpiv, dpiv, bevel=0.0008, smooth=45)
    # ригели: цилиндры в торце дверцы, выступают в карманы (10 мм)
    rb = bmesh.new()
    for z in rig_z:
        cyl(rb, (dw1 - 0.04, yf + 0.02, z), (dw1 + 0.0105, yf + 0.02, z), 0.0085, segs=20)
    for z in ded_z:
        cyl(rb, (dw0 + 0.03, yf + 0.02, z), (dw0 + 0.0005, yf + 0.02, z), 0.0085, segs=20)
    part(rb, "СН_ригели", coll, [m["chrome"]], door, dpiv, dpiv, smooth=50)
    # петли: цилиндры-штыри на лицевой стороне слева (на двери), листы на раме; штырь — общий, виден снаружи
    hb = bmesh.new()
    for z in (0.14, 0.36, 0.58):
        cyl(hb, (dpiv[0], dpiv[1], z - 0.025), (dpiv[0], dpiv[1], z + 0.025), 0.0065, segs=16)
        L.bm_box(hb, (dpiv[0] - 0.0045, yf - 0.012, z - 0.025), (dw0 + 0.012, yf + 0.001, z + 0.025))
    part(hb, "СН_петли_дверца", coll, [m["chrome"]], door, dpiv, dpiv, bevel=0.001, smooth=50)
    pb = bmesh.new()
    for z in (0.14, 0.36, 0.58):
        cyl(pb, (dpiv[0], dpiv[1], z - 0.0285), (dpiv[0], dpiv[1], z - 0.0255), 0.0045, segs=12)
        cyl(pb, (dpiv[0], dpiv[1], z + 0.0255), (dpiv[0], dpiv[1], z + 0.0285), 0.0045, segs=12)
        L.bm_box(pb, (-hw, yf - 0.012, z - 0.0285), (dpiv[0] - 0.0045, yf + 0.0, z + 0.0285))
    lc.obj(pb, "СН_петли_корпус", coll, [m["chrome"]], r, bevel=0.0008, smooth=50)
    # лимб кодового замка: накладка, кольцо с рисками, ручка-набор (всё на лице двери, неподвижно)
    dc = (0.0, yf - 0.0, 0.50)
    lb = bmesh.new()
    lathe_y(lb, [(0.0, 0.0), (0.048, 0.0), (0.048, 0.004), (0.045, 0.0055), (0.0, 0.0055)], dc)
    mid_prof = [(0.0, 0.0055), (0.040, 0.0055), (0.040, 0.0085), (0.0375, 0.0095), (0.030, 0.0095), (0.030, 0.0125),
                (0.027, 0.014), (0.0, 0.014)]
    lathe_y(lb, mid_prof, dc)
    # риски: 50 штук на кольце r 0.0375…0.040, каждая пятая длиннее — рельеф на ободе лимба
    for i in range(50):
        a = math.tau * i / 50
        ln = 0.0042 if i % 5 == 0 else 0.0028
        ux, uz = math.sin(a), math.cos(a)
        ax = V((ux, 0, uz))
        p = V(dc) + ax * (0.0396 - ln) + V((0, -0.0095, 0))
        tx = V((uz, 0, -ux))
        pts = [p + tx * 0.0004, p - tx * 0.0004, p - tx * 0.0004 + ax * ln, p + tx * 0.0004 + ax * ln]
        vb = [lb.verts.new(q) for q in pts]
        vt = [lb.verts.new(q + V((0, -0.0007, 0))) for q in pts]
        lb.faces.new(vb[::-1]); lb.faces.new(vt)
        for k in range(4):
            lb.faces.new((vb[k], vb[(k + 1) % 4], vt[(k + 1) % 4], vt[k]))
    # указатель-треугольник над лимбом
    L.bm_prism(lb, [(-0.004, 0), (0.004, 0), (0, -0.007)], V((dc[0], dc[1] - 0.0055, dc[2] + 0.054)), (1, 0, 0), (0, 0, 1), (0, -0.0015, 0))
    part(lb, "СН_лимб", coll, [m["chrome"]], door, dpiv, dpiv, bevel=0.0004, segs=1, smooth=50)
    # штурвал: ступица со штоком и три спицы с шариками; вращается вокруг оси Y
    hc = (0.0, yf, 0.26)
    wb = bmesh.new()
    lathe_y(wb, [(0.0, 0.0), (0.020, 0.0), (0.020, 0.012), (0.017, 0.017), (0.0, 0.017)], hc)
    for k in range(3):
        a = math.radians(90 + 120 * k)
        ax = V((math.cos(a), 0, math.sin(a)))
        p0 = V(hc) + V((0, -0.011, 0))
        p1 = p0 + ax * 0.060
        cyl(wb, p0 + ax * 0.012, p1, 0.0052, segs=14, r1=0.0044)
        lc.L.bm_sphere(wb, p1, 0.0105, segs=14, rings=8)
    whl = part(wb, "СН_ручка_штурвал", coll, [m["chrome"]], door, dpiv, hc, smooth=50, mover=True)
    # --- трейзер: дверца в своих петлях (слева), накладка замка
    tz0, tz1 = zt0 + 0.001, zt1 - 0.001
    tpiv = (-0.243, -0.167, 0.0)
    tw = 0.486
    tb2 = bmesh.new()
    lc.rbox(tb2, (tw, 0.004, tz1 - tz0), 0.002, (0.0, -0.167, (tz0 + tz1) / 2), seg=2)
    # окантовка по периметру дверцы трейзера (штамповка)
    for (x0, x1, z0_, z1_) in ((-tw / 2, tw / 2, tz1 - 0.012, tz1), (-tw / 2, tw / 2, tz0, tz0 + 0.012)):
        L.bm_box(tb2, (x0, -0.167 - 0.007, z0_), (x1, -0.167 - 0.004 + 0.0, z1_))
    L.bm_box(tb2, (tw / 2 - 0.012, -0.167 - 0.007, tz0), (tw / 2, -0.167 - 0.004 + 0.0, tz1))
    L.bm_box(tb2, (-tw / 2, -0.167 - 0.007, tz0), (-tw / 2 + 0.012, -0.167 - 0.004 + 0.0, tz1))
    lc.L.bm_cyl(tb2, (tw / 2 - 0.045, -0.167 - 0.004, (tz0 + tz1) / 2), (tw / 2 - 0.045, -0.167 - 0.011, (tz0 + tz1) / 2), 0.012, segs=20)
    plug(tb2, (tw / 2 - 0.045, -0.167 - 0.011, (tz0 + tz1) / 2), depth=0.003, r=0.0055, axis="-y")
    # ригель-язычок замка и петли
    L.bm_box(tb2, (tw / 2 - 0.004, -0.167 + 0.0, tz0 + 0.03), (tw / 2 + 0.003, -0.167 + 0.006, tz1 - 0.03))
    for z in (tz0 + 0.025, tz1 - 0.025):
        cyl(tb2, (-tw / 2 + 0.004, -0.167 + 0.0, z - 0.015), (-tw / 2 + 0.004, -0.167 + 0.0, z + 0.015), 0.0045, segs=12)
    tdoor = part(tb2, "СН_трейзер_дверца", coll, [m["steel_b"]], r, (0, 0, 0), tpiv, bevel=0.0008, smooth=45, mover=True)
    if open_:
        _rot_z(door, -105)
        _rot_z(tdoor, -28)
    return r


# ================================================================ сейф-ячейка настенный

def wall_cell(coll, m, at, open_: bool):
    """Сейф-ячейка встраиваемый 360 × 260 × 240: коробка листа 2 мм, фланец по периметру, дверца на внутренней
    петле (две скрытые петли-рычага), ключевой замок с накладкой и поворотная ручка, внутри полка.
    Корень — на плоскости фланца (лицо к −Y, коробка уходит в стену к +Y), низ фланца."""
    r = L.root("СЯ_сейф_ячейка" + ("_открыт" if open_ else ""), coll, at)
    FW, FH, fl = 0.36, 0.26, 0.003            # фланец
    bw, bh, bd = 0.300, 0.200, 0.237          # коробка
    zc = FH / 2
    bx = shell_part("СЯ_коробка", coll, [m["steel_c"]], r, (bw, bd, bh), 0.004, (0, bd / 2, zc), "-y", 0.002)
    # фланец: рамка 3 мм с отбортовкой кромки
    fb = bmesh.new()
    gx, gz = (FW - bw) / 2 - 0.003, (FH - bh) / 2 - 0.003  # ширина кромки рамки
    ow, oh = FW, FH
    iw, ih = bw - 0.006, bh - 0.006
    L.bm_box(fb, (-ow / 2, -fl, 0), (ow / 2, 0, (oh - ih) / 2))
    L.bm_box(fb, (-ow / 2, -fl, (oh + ih) / 2), (ow / 2, 0, oh))
    L.bm_box(fb, (-ow / 2, -fl, (oh - ih) / 2), (-iw / 2, 0, (oh + ih) / 2))
    L.bm_box(fb, (iw / 2, -fl, (oh - ih) / 2), (ow / 2, 0, (oh + ih) / 2))
    # отбортовка в проём (хромированный ободок 2 мм)
    L.bm_box(fb, (-iw / 2, -fl, (oh - ih) / 2), (iw / 2, 0, (oh - ih) / 2 + 0.0025))
    lc.obj(fb, "СЯ_фланец", coll, [m["steel_a"]], r, bevel=0.0009, segs=2, smooth=45)
    # полка
    sb = bmesh.new()
    lc.rbox(sb, (bw - 0.006, bd - 0.07, 0.004), 0.0015, (0, 0.11 + 0.01, zc - 0.015), seg=2)
    lc.obj(sb, "СЯ_полка", coll, [m["steel_c"]], r, smooth=50)
    # скрытая петля: ось внутри проёма, у левого края
    dw, dh, dd = iw - 0.004, ih - 0.004, 0.030
    pv = (-dw / 2 - 0.005, -0.002, 0.0)
    cx, cz = 0.0, zc
    door = shell_part("СЯ_дверца", coll, [m["steel_a"]], r, (dw, dd, dh), 0.004, (cx, 0.0 + dd / 2 - 0.004, cz), "+y", 0.002, piv=pv, mover=True)
    # внутренний лист и ригель
    ib = bmesh.new()
    lc.rbox(ib, (dw - 0.016, 0.003, dh - 0.016), 0.0015, (cx, dd - 0.014, cz), seg=2)
    L.bm_box(ib, (dw / 2 - 0.075, dd - 0.0125, cz - 0.03), (dw / 2 - 0.02, dd - 0.0125 + 0.008, cz + 0.03))
    part(ib, "СЯ_дверца_лист", coll, [m["steel_raw"]], door, pv, pv, bevel=0.0007, smooth=45)
    rb = bmesh.new()
    cyl(rb, (dw / 2 - 0.05, dd - 0.016, cz + 0.0), (dw / 2 + 0.0095, dd - 0.016, cz + 0.0), 0.0062, segs=18)
    part(rb, "СЯ_ригель", coll, [m["chrome"]], door, pv, pv, smooth=50)
    # петли: рычаги на двери (за лицом) к оси у лицевой плоскости, корпусные звенья на фланце
    hb = bmesh.new()
    for z in (cz - 0.065, cz + 0.065):
        L.bm_box(hb, (pv[0], -0.0022, z - 0.012), (-dw / 2 + 0.03, 0.0006, z + 0.012))
        cyl(hb, (pv[0], pv[1], z - 0.012), (pv[0], pv[1], z + 0.012), 0.0034, segs=12)
    part(hb, "СЯ_петли_дверца", coll, [m["steel_raw"]], door, pv, pv, bevel=0.0005, smooth=50)
    kb = bmesh.new()
    for z in (cz - 0.065, cz + 0.065):
        for dz in (-0.0135, 0.0135):
            cyl(kb, (pv[0], pv[1], z + dz - 0.0015), (pv[0], pv[1], z + dz + 0.0015), 0.0034, segs=12)
        L.bm_box(kb, (pv[0] - 0.003, -0.0022, z - 0.016), (pv[0] + 0.003, 0.0006, z + 0.016))
    lc.obj(kb, "СЯ_петли_корпус", coll, [m["steel_raw"]], r, bevel=0.0003, smooth=50)
    # замок: накладка со скруглением, личинка с пазом; поворотная ручка — рычаг на штоке
    lk = bmesh.new()
    lcx, lcz = dw / 2 - 0.045, cz
    lc.rbox(lk, (0.034, 0.003, 0.054), 0.007, (lcx, -0.0055, lcz), seg=3)
    L.bm_cyl(lk, (lcx, -0.004, lcz), (lcx, -0.0075, lcz), 0.0105, segs=20)
    plug(lk, (lcx, -0.0075, lcz), depth=0.0015, r=0.0062, axis="-y")
    part(lk, "СЯ_замок", coll, [m["chrome"]], door, pv, pv, bevel=0.0005, smooth=50)
    hp = (-0.045, -0.004, cz)
    hb2 = bmesh.new()
    lc.lathe(hb2, [(0.0, 0.0), (0.0145, 0.0), (0.0145, 0.003), (0.012, 0.005), (0.0, 0.005)], segs=24, origin=hp, axis=(0, -1, 0))
    lc.rbox(hb2, (0.060, 0.010, 0.017), 0.0045, (hp[0], hp[1] - 0.010, hp[2]), seg=3)
    cyl(hb2, (hp[0], hp[1] - 0.004, hp[2]), (hp[0], hp[1] - 0.007, hp[2]), 0.006, segs=14)
    part(hb2, "СЯ_ручка", coll, [m["chrome"]], door, pv, hp, smooth=50, mover=True)
    if open_:
        _rot_z(door, -110)
    return r
