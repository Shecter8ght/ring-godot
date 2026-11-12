"""Кассовое место: денежный ящик с выдвижным лотком и кассовый аппарат-моноблок на нём."""
import math

import bmesh
from mathutils import Matrix

import lc
from lc import L, V, part, shell_part, cyl, plug, rot_box


def cash_place(coll, m, at, open_: bool):
    """Денежный ящик 410 × 100 × 420: корпус из листа 1 мм, лоток на направляющих (5 отделений для купюр с прижимами,
    8 ячеек для монет, замок с личинкой), щель для чеков в лицевой планке; сверху аппарат-моноблок 360 × 300 × 400:
    корпус с наклонной клавиатурой (отдельные клавиши), принтер с окном чековой ленты и зубчатым отрывом, дисплей
    кассира на стойке, поворотный дисплей покупателя. Корень — середина основания ящика на столе."""
    r = L.root("КМ_кассовое_место" + ("_лоток_выдвинут" if open_ else ""), coll, at)
    W, H, D = 0.41, 0.10, 0.42
    yf = -D / 2
    hw = W / 2
    # ---- денежный ящик
    hs = shell_part("КМ_ящик_корпус", coll, [m["steel_c"]], r, (W, D, H), 0.006, (0, 0, H / 2), "-y", 0.001, seg=2, flat=(1, 2, 0))
    fb = bmesh.new()
    # лицевая планка над лотком с щелью для чеков (окно 150 × 6 мм)
    lc.hole_plate(fb, -hw, hw, 0.087, H, yf - 0.0015, yf, (-0.075, 0.075, 0.0905, 0.0965))
    L.bm_box(fb, (-hw, yf - 0.0015, 0.0), (-hw + 0.006, yf, 0.087))
    L.bm_box(fb, (hw - 0.006, yf - 0.0015, 0.0), (hw, yf, 0.087))
    L.bm_box(fb, (-hw + 0.006, yf - 0.0015, 0.0), (hw - 0.006, yf, 0.006))
    lc.obj(fb, "КМ_ящик_планка", coll, [m["steel_c"]], r, bevel=0.0004, segs=1, smooth=45)
    # неподвижные рельсы
    rf = bmesh.new()
    for s in (-1, 1):
        x0, x1 = (s * (hw - 0.012), s * (hw - 0.006))
        L.bm_box(rf, (min(x0, x1), yf + 0.01, 0.025), (max(x0, x1), -yf - 0.02, 0.075))
    lc.obj(rf, "КМ_ящик_рельсы_корпус", coll, [m["steel_raw"]], r, bevel=0.0004, segs=1, smooth=45)
    # лоток: лицо — на панели, коробка и вставка — дочерние
    pw, ph = W - 0.014, 0.078
    pz0 = 0.008
    tpiv = (0.0, yf, pz0 + ph / 2)
    pb = bmesh.new()
    lc.rbox(pb, (pw, 0.022, ph), 0.004, (0.0, yf + 0.011 - 0.0003, pz0 + ph / 2), seg=2)
    # выемка-ручка (пальцевая) сверху лица — утопленный валик, и замок справа
    L.bm_cyl(pb, (-0.06, yf - 0.0003, pz0 + ph - 0.012), (0.06, yf - 0.0003, pz0 + ph - 0.012), 0.0045, segs=12)
    L.bm_box(pb, (-0.06, yf - 0.001, pz0 + ph - 0.016), (0.06, yf + 0.0003, pz0 + ph - 0.008))
    L.bm_cyl(pb, (pw / 2 - 0.035, yf - 0.0003, pz0 + ph / 2 - 0.006), (pw / 2 - 0.035, yf - 0.004, pz0 + ph / 2 - 0.006), 0.0105, segs=22)
    plug(pb, (pw / 2 - 0.035, yf - 0.004, pz0 + ph / 2 - 0.006), depth=0.0015, r=0.0062, axis="-y")
    tray = part(pb, "КМ_лоток_лицо", coll, [m["plastic_beige"]], r, (0, 0, 0), tpiv, bevel=0.0005, segs=1, smooth=45, mover=True)
    bw, bd, bh = W - 0.040, 0.372, 0.040
    by0 = yf + 0.022
    z0t = 0.016
    box = shell_part("КМ_лоток_коробка", coll, [m["steel_raw"]], tray, (bw, bd, bh), 0.004, (0, by0 + bd / 2, z0t + bh / 2), "+z", 0.0008,
                     ppiv=tpiv, piv=tpiv, seg=2, flat=(1, 2, 0), bevel=0.0003)
    # вставка: дно с перегородками; купюры сзади (5 щелей), монеты спереди (8 ячеек)
    ib = bmesh.new()
    zf = z0t + 0.003
    iw = bw - 0.008
    L.bm_box(ib, (-iw / 2, by0 + 0.004, zf - 0.003), (iw / 2, by0 + bd - 0.004, zf))
    ybs = by0 + 0.130   # граница монетной и купюрной частей
    # продольные стенки купюрных щелей
    for k in range(6):
        x = -iw / 2 + k * iw / 5
        L.bm_box(ib, (x - 0.0015 if 0 < k < 5 else (x if k == 0 else x - 0.003), ybs, zf),
                 (x + 0.0015 if 0 < k < 5 else (x + 0.003 if k == 0 else x), by0 + bd - 0.004, zf + 0.034))
    L.bm_box(ib, (-iw / 2, ybs - 0.003, zf), (iw / 2, ybs, zf + 0.020))
    # монетные ячейки: поперечные стенки между 8 ячейками
    for k in range(9):
        x = -iw / 2 + k * iw / 8
        a0 = x - 0.0015 if 0 < k < 8 else (x if k == 0 else x - 0.003)
        a1 = x + 0.0015 if 0 < k < 8 else (x + 0.003 if k == 0 else x)
        L.bm_box(ib, (a0, by0 + 0.004, zf), (a1, ybs, zf + 0.026))
    L.bm_box(ib, (-iw / 2, by0 + 0.004, zf), (iw / 2, by0 + 0.007, zf + 0.026))
    part(ib, "КМ_лоток_вставка", coll, [m["plastic_black"]], tray, tpiv, tpiv, bevel=0.0004, segs=1, smooth=45)
    # прижимы купюр: проволочные дужки через каждую щель
    wb = bmesh.new()
    for k in range(5):
        cx = -iw / 2 + (k + 0.5) * iw / 5
        yb = by0 + bd - 0.006
        L.bm_box(wb, (cx - 0.003, yb - 0.002, zf + 0.030), (cx + 0.003, yb + 0.002, zf + 0.036))
        lc.B.pipe(wb, [(cx, yb, zf + 0.034), (cx, yb - 0.05, zf + 0.0345), (cx, ybs + 0.05, zf + 0.0345),
                       (cx, ybs + 0.045, zf + 0.0225), (cx, ybs + 0.075, zf + 0.0225)], 0.0013, segs=8, bend=0.006)
    part(wb, "КМ_лоток_прижимы", coll, [m["chrome"]], tray, tpiv, tpiv, smooth=50)
    # направляющие лотка (подвижная часть)
    rb = bmesh.new()
    for s in (-1, 1):
        x0, x1 = (s * (bw / 2), s * (bw / 2 + 0.0055))
        L.bm_box(rb, (min(x0, x1), by0 + 0.02, 0.025), (max(x0, x1), by0 + bd - 0.02, 0.075 - 0.01))
    part(rb, "КМ_лоток_рельсы", coll, [m["steel_raw"]], tray, tpiv, tpiv, bevel=0.0004, segs=1, smooth=45)
    if open_:
        tray.location = V(tpiv) + V((0, -0.30, 0))
    # ================= кассовый аппарат
    zb = H
    rb2 = bmesh.new()
    poly = [(-0.20, 0.0), (0.20, 0.0), (0.20, 0.10), (0.05, 0.10), (0.03, 0.078), (-0.20, 0.035)]
    L.bm_prism(rb2, poly, V((-0.18, 0, zb)), (0, 1, 0), (0, 0, 1), (0.36, 0, 0))
    base = lc.obj(rb2, "КМ_аппарат_корпус", coll, [m["plastic_beige"]], r, bevel=0.004, segs=3, angle=35.0, smooth=40)
    # прорези-швы корпуса: пояс-накладка (стык половин) — тонкая рельефная полоса по периметру
    # клавиатура: 6 рядов × 12 клавиш по наклонной деке
    kb = bmesh.new()
    p0 = V((0, -0.20, zb + 0.035))
    p1 = V((0, 0.03, zb + 0.078))
    sl = p1 - p0
    tilt = math.atan2(sl.z, sl.y)
    for row in range(6):
        for col in range(12):
            u = 0.018 + row * 0.0345
            p = p0 + sl.normalized() * u
            x = -0.15 + col * 0.0273
            rot_box(kb, (x - 0.0105, p.y - 0.0125, p.z + 0.0005), (x + 0.0105, p.y + 0.0125, p.z + 0.0085), (x, p.y, p.z), Matrix.Rotation(tilt, 3, "X"))
    lc.obj(kb, "КМ_клавиатура", coll, [m["plastic_black"]], r, bevel=0.0012, segs=2, smooth=45)
    # окно принтера и крышка рулона
    pr = bmesh.new()
    px0, px1, py0, py1 = -0.095, 0.045, 0.02, 0.185
    lc.rbox(pr, (px1 - px0, py1 - py0, 0.050), 0.006, ((px0 + px1) / 2, (py0 + py1) / 2, zb + 0.100 + 0.025 - 0.0), seg=3)
    lc.obj(pr, "КМ_принтер_крышка", coll, [m["plastic_beige"]], r, bevel=0.0, smooth=45)
    wd = bmesh.new()
    lc.rbox(wd, (0.105, 0.115, 0.0035), 0.0012, ((px0 + px1) / 2, 0.115, zb + 0.150 + 0.0003), seg=2)
    lc.obj(wd, "КМ_принтер_окно", coll, [m["glass_dark"]], r, smooth=45)
    # рулон за окном (виден сквозь стекло) и зубчатая планка отрыва
    ro = bmesh.new()
    cyl(ro, ((px0 + px1) / 2 - 0.028, 0.125, zb + 0.130), ((px0 + px1) / 2 + 0.028, 0.125, zb + 0.130), 0.028, segs=28)
    lc.obj(ro, "КМ_принтер_рулон", coll, [m["paper"]], r, smooth=50)
    tb = bmesh.new()
    L.bm_box(tb, (px0 + 0.01, py0 - 0.006, zb + 0.131), (px1 - 0.01, py0 + 0.0005, zb + 0.139))
    n_t = 36
    xt0, xt1 = (px0 + px1) / 2 - 0.03, (px0 + px1) / 2 + 0.03
    for i in range(n_t):
        x = xt0 + (xt1 - xt0) * i / n_t
        L.bm_prism(tb, [(0, 0), ((xt1 - xt0) / n_t, 0), ((xt1 - xt0) / n_t / 2, 0.003)], V((x, py0 - 0.0058, zb + 0.139)), (1, 0, 0), (0, 0, 1), (0, 0.0016, 0))
    lc.obj(tb, "КМ_принтер_отрыв", coll, [m["steel_raw"]], r, bevel=0.0, smooth=50)
    # чековая лента: выходит из щели и свисает вперёд
    pb2 = bmesh.new()
    cx = (px0 + px1) / 2
    path = lc.smooth_path([(cx, 0.06, zb + 0.145), (cx, 0.02, zb + 0.146), (cx, -0.02, zb + 0.140), (cx, -0.05, zb + 0.124), (cx, -0.062, zb + 0.106)], 6)
    L.bm_sweep(pb2, path, [(-0.028, 0.0), (0.028, 0.0), (0.028, 0.0004), (-0.028, 0.0004)], up=(0, 0, 1))
    lc.obj(pb2, "КМ_чековая_лента", coll, [m["paper"]], r, smooth=45)
    # дисплей кассира: стойка на шарнире, панель и экран
    sx, sy = 0.115, 0.13
    sb = bmesh.new()
    cyl(sb, (sx, sy, zb + 0.100), (sx, sy, zb + 0.108), 0.040, segs=28, r1=0.036)
    cyl(sb, (sx, sy, zb + 0.108), (sx, sy, zb + 0.185), 0.013, segs=18)
    lc.L.bm_sphere(sb, (sx, sy, zb + 0.190), 0.016, segs=18, rings=10)
    lc.obj(sb, "КМ_дисплей_кассира_стойка", coll, [m["plastic_black"]], r, smooth=50)
    db = bmesh.new()
    rot = Matrix.Rotation(math.radians(-14), 3, "X")
    c0 = V((sx, sy + 0.012, zb + 0.245))
    for (sz, mt, off) in (((0.17, 0.014, 0.112), "b", 0.0), ):
        n0 = len(db.verts)
        lc.rbox(db, sz, 0.005, (0, 0, 0), seg=3)
        db.verts.ensure_lookup_table()
        for v in db.verts[n0:]:
            v.co = c0 + rot @ v.co
    lc.obj(db, "КМ_дисплей_кассира_корпус", coll, [m["plastic_black"]], r, smooth=45)
    sc_ = bmesh.new()
    n0 = len(sc_.verts)
    lc.rbox(sc_, (0.150, 0.0016, 0.090), 0.002, (0, -0.0072, 0), seg=2)
    sc_.verts.ensure_lookup_table()
    for v in sc_.verts[n0:]:
        v.co = c0 + rot @ v.co
    lc.obj(sc_, "КМ_дисплей_кассира_экран", coll, [m["screen"]], r, smooth=45)
    # дисплей покупателя: стойка (неподвижная) и головка (поворотная вокруг стойки)
    cx2, cy2 = -0.145, 0.155
    pl = bmesh.new()
    cyl(pl, (cx2, cy2, zb + 0.100), (cx2, cy2, zb + 0.106), 0.030, segs=24, r1=0.027)
    cyl(pl, (cx2, cy2, zb + 0.106), (cx2, cy2, zb + 0.235), 0.0085, segs=16)
    lc.obj(pl, "КМ_дисплей_покупателя_стойка", coll, [m["plastic_black"]], r, smooth=50)
    hd = bmesh.new()
    cyl(hd, (cx2, cy2, zb + 0.230), (cx2, cy2, zb + 0.242), 0.014, segs=18)
    n0 = len(hd.verts)
    lc.rbox(hd, (0.12, 0.014, 0.060), 0.004, (cx2, cy2 - 0.014, zb + 0.268), seg=3)
    L.bm_box(hd, (cx2 - 0.004, cy2 - 0.014, zb + 0.238), (cx2 + 0.004, cy2, zb + 0.262))
    hdo = part(hd, "КМ_дисплей_покупателя", coll, [m["plastic_black"]], r, (0, 0, 0), (cx2, cy2, zb + 0.236), bevel=0.0, smooth=45, mover=True)
    he = bmesh.new()
    lc.rbox(he, (0.100, 0.0016, 0.044), 0.002, (cx2, cy2 - 0.0215, zb + 0.268), seg=2)
    part(he, "КМ_дисплей_покупателя_экран", coll, [m["screen"]], hdo, (cx2, cy2, zb + 0.236), (cx2, cy2, zb + 0.236), smooth=45)
    return r
