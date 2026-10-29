# AR-15: ствол 11.5″ с муфтой (боевые упоры), газовый блок и трубка, гайка цевья, восьмигранное цевьё M-LOK
# с верхней планкой в линию ресивера, упор для ладони снизу и короткая боковая планка спереди слева (как у листинга Fab).
import math
import bpy
from lib import (MM, UPPER_FRONT, RAIL_TOP, GAS_Z, BARREL_LEN, THREAD_X, BARREL_R_FRONT, GAS_BLOCK_X, HG_X, HG_HALF_W,
                 HG_BOTTOM, MLOK_PITCH, fillet, arc_pts, prism_xz, prism_yz, prism_xy, box, cyl, lathe, boolean, finish,
                 bevel_edges, auto_sharp, apply_transform, set_parent)
from part_upper import RAIL_BASE, FRONT_RING_LEN, rail, rail_profile

EXT_X = (-14.0, UPPER_FRONT + FRONT_RING_LEN + 2.0)   # муфта ствола: упоры сзади, фланец у торца кольца
NUT_X = (UPPER_FRONT + FRONT_RING_LEN - 13.0, 60.0)
BORE_R = 2.85
WALL = 2.6
HG_INNER_TOP = 20.6
MLOK_LEN, MLOK_H = 32.0, 7.0


def hg_outer():
    w, b = HG_HALF_W, HG_BOTTOM
    return [(-9.5, RAIL_BASE), (-w, RAIL_BASE - (w - 9.5)), (-w, -10.5), (-(w - 10.5), b), ((w - 10.5), b), (w, -10.5),
            (w, RAIL_BASE - (w - 9.5)), (9.5, RAIL_BASE)]


def hg_inner():
    w, b = HG_HALF_W - WALL, HG_BOTTOM + WALL
    k1 = (HG_HALF_W + RAIL_BASE - (HG_HALF_W - 9.5)) - WALL * math.sqrt(2)     # верхняя фаска: y + z = k1
    k2 = (HG_HALF_W + 10.5) - WALL * math.sqrt(2)                               # нижняя: y − z = k2
    return [(-(k1 - HG_INNER_TOP), HG_INNER_TOP), (-w, k1 - w), (-w, w - k2), (-(k2 + b), b), ((k2 + b), b), (w, w - k2),
            (w, k1 - w), ((k1 - HG_INNER_TOP), HG_INNER_TOP)]


def mlok_slot(name, xc, C, depth_axis, plane, sign=1, length=MLOK_LEN, h=MLOK_H):
    """Резак паза M-LOK (7 × 32, скруглённые концы) поперёк грани. plane — координата грани по оси depth_axis."""
    pts = fillet([(xc - length / 2, -h / 2), (xc + length / 2, -h / 2), (xc + length / 2, h / 2), (xc - length / 2, h / 2)], h / 2 - 0.01, 6)
    if depth_axis == "Y":   # боковая грань: профиль в XZ (z по второй координате, центр z=0.5)
        return prism_xz(name, [(x, z + 0.5) for x, z in pts], plane - 6 * sign, plane + 6 * sign, C)
    return prism_xy(name, [(x, y) for x, y in pts], plane - 6, plane + 6, C)   # низ: профиль в XY


def build(ctx):
    Bc = ctx["coll"]["Barrel"]
    Hc = ctx["coll"]["Handguard"]
    o = {}
    # --- ствол: патронная часть толще, посадка газового блока Ø0.75″, перед Ø0.625″, резьба 1/2-28 ---
    gx0, gx1 = GAS_BLOCK_X
    prof = [(EXT_X[1] - 4.0, BORE_R), (EXT_X[1] - 4.0, 11.6), (64.0, 11.6), (76.0, 9.525), (gx1 + 1.0, 9.525), (gx1 + 3.0, BARREL_R_FRONT),
            (THREAD_X[0], BARREL_R_FRONT), (THREAD_X[0], 6.35), (BARREL_LEN - 0.8, 6.35), (BARREL_LEN, 5.6), (BARREL_LEN, 3.4),
            (BARREL_LEN - 0.6, BORE_R)]
    barrel = lathe("Barrel", prof, Bc, "Steel_black", seg=64)
    # нитки резьбы (кольцевые проточки)
    for k in range(int((THREAD_X[1] - THREAD_X[0] - 2) / 0.907)):
        xx = THREAD_X[0] + 1.2 + k * 0.907
        boolean(barrel, lathe("cut_thread", [(xx - 0.25, 5.95), (xx, 6.5), (xx + 0.25, 5.95)], Bc, None, seg=48))
    # газоотводное отверстие под блоком
    boolean(barrel, cyl("cut_gas_port", 0.0, 12.0, 1.0, Bc, seg=12, cy=(gx0 + gx1) / 2, cz=0, axis="Z"))
    auto_sharp(barrel, 35)
    o["barrel"] = barrel
    # муфта ствола в ресивере: внутри упоры под затвор, снизу скосы подачи
    ext = lathe("Barrel_extension", [(EXT_X[0], 6.9), (EXT_X[0], 12.2), (EXT_X[1] - 3.0, 12.2), (EXT_X[1] - 3.0, 13.4), (EXT_X[1], 13.4),
                                     (EXT_X[1], 4.8), (0.2, 4.8), (0.2, 7.8), (-8.9, 7.8), (-8.9, 6.9)],
                Bc, "Steel_black", seg=64)
    # пазы между упорами муфты (через них проходят упоры затвора в положении «отперто»)
    for k in range(8):
        a = 45.0 * k
        c = box("cut_ext_lug", EXT_X[0] - 1.0, -8.8, -1.75, 1.75, 6.0, 7.8, Bc)
        c.rotation_euler = (math.radians(a), 0, 0)
        apply_transform(c)
        boolean(ext, c)
    # скосы подачи снизу (M4)
    for s in (-1, 1):
        r = box("cut_ramp", EXT_X[0] - 2, 2.0, -3.4, 3.4, -14.0, -5.0, Bc)
        r.rotation_euler = (math.radians(18 * s), math.radians(-28), 0)
        r.location = (EXT_X[0] * MM, 0, 0)
        apply_transform(r)
        boolean(ext, r)
    # штифт-указатель и отверстие газовой трубки во фланце
    boolean(ext, cyl("cut_ext_gas", EXT_X[1] - 4, EXT_X[1] + 1, 2.6, Bc, seg=16, cz=GAS_Z))
    auto_sharp(ext, 35)
    o["extension"] = ext
    # --- газовый блок низкого профиля и трубка ---
    gb = prism_yz("Gas_block", fillet([(-11.0, -10.8), (11.0, -10.8), (11.0, 13.0), (5.6, 20.0), (-5.6, 20.0), (-11.0, 13.0)],
                                      [3.0, 3.0, 2.0, 2.5, 2.5, 2.0], 5), gx0, gx1, Bc, "Steel_black")
    boolean(gb, cyl("cut_gb_bore", gx0 - 2, gx1 + 2, 9.6, Bc, seg=48))
    boolean(gb, cyl("cut_gb_tube", gx0 - 2, gx1 - 6.0, 2.45, Bc, seg=20, cz=GAS_Z))
    for xs in (gx0 + 7.0, gx1 - 7.0):
        boolean(gb, cyl("cut_gb_set", -16, -9, 1.6, Bc, seg=16, cy=xs, cz=0, axis="Z"))
    boolean(gb, cyl("cut_gb_pin", -14, 14, 0.8, Bc, seg=12, cy=gx0 + 4.5, cz=GAS_Z, axis="Y"))
    finish(gb, w=0.35, seg=2, angle=35)
    o["gas_block"] = gb
    tube = lathe("Gas_tube", [(-30.0, 1.4), (-30.0, 2.15), (-29.2, 2.4), (gx1 - 7.0, 2.4), (gx1 - 7.0, 1.4)], Bc, "Steel_black", seg=24, cz=GAS_Z)
    o["gas_tube"] = tube
    o["gas_pin"] = cyl("Gas_tube_pin", -11.2, 11.2, 0.75, Bc, "Steel_black", seg=12, cy=gx0 + 4.5, cz=GAS_Z, axis="Y", ch=0.2)
    # --- гайка цевья (под цевьём): шлицы под ключ, проход трубки сверху ---
    nut = lathe("Barrel_nut", [(NUT_X[0], 12.2), (NUT_X[0], 17.0), (NUT_X[1], 17.0), (NUT_X[1], 11.0), (NUT_X[0] + 13.0, 11.0),
                               (NUT_X[0] + 13.0, 12.2)], Hc, "Steel_black", seg=64)
    boolean(nut, box("cut_nut_tube", NUT_X[0] - 1, NUT_X[1] + 1, -3.2, 3.2, 12.0, 20.0, Hc))
    for k in range(1, 8):
        a = 45.0 * k
        c = box("cut_nut_spline", NUT_X[1] - 6.0, NUT_X[1] + 1, -2.0, 2.0, 15.0, 18.0, Hc)
        c.rotation_euler = (math.radians(a), 0, 0)
        apply_transform(c)
        boolean(nut, c)
    auto_sharp(nut, 35)
    o["nut"] = nut
    o.update(handguard(Hc))
    return o


def handguard(Hc):
    o = {}
    x0, x1 = HG_X
    outer = hg_outer()
    hg = prism_yz("Handguard", outer, x0, x1, Hc, "Alu_anodized")
    # нос: низ короче верха — скос вперёд снизу, «зубец» по бокам
    nose = prism_xz("cut_nose", [(x1 - 9.0, HG_BOTTOM - 5), (x1 + 5, HG_BOTTOM - 5), (x1 + 5, -2.0), (x1 - 1.0, -2.0)], -30, 30, Hc)
    boolean(hg, nose)
    boolean(hg, prism_yz("cut_hg_in", hg_inner(), x0 - 1, x1 + 1, Hc))
    # хомут сзади: две поперечные стяжки снизу; вырез под фланец гайки
    for xs in (x0 + 9.0, x0 + 19.0):
        boolean(hg, cyl("cut_clamp", -30, 30, 2.1, Hc, seg=16, cy=xs, cz=-13.5, axis="Y"))
        boolean(hg, cyl("cut_clamp_cb", HG_HALF_W - 1.6, HG_HALF_W + 3, 3.4, Hc, seg=24, cy=xs, cz=-13.5, axis="Y"))
    boolean(hg, box("cut_clamp_split", x0 - 1, x0 + 26.0, -0.8, 0.8, HG_BOTTOM - 3, HG_BOTTOM + WALL + 0.5, Hc))
    # пазы M-LOK: по бокам и снизу; облегчающие прорези на верхних фасках
    xs = []
    xc = x1 - 26.0
    while xc - MLOK_LEN / 2 > x0 + 30.0:
        xs.append(xc)
        xc -= MLOK_PITCH
    for i, xc in enumerate(xs):
        for s in (-1, 1):
            boolean(hg, mlok_slot(f"cut_mlok_s{s}{i}", xc, Hc, "Y", HG_HALF_W * s, s))
        boolean(hg, mlok_slot(f"cut_mlok_b{i}", xc, Hc, "Z", HG_BOTTOM))
    for i, xc in enumerate(xs):
        for s in (-1, 1):
            c = prism_xz(f"cut_top_slot{s}{i}", fillet([(xc - 15.0, -2.4), (xc + 15.0, -2.4), (xc + 15.0, 2.4), (xc - 15.0, 2.4)], 2.3, 6),
                         -6, 6, Hc)
            # прорезь на фаске 45°: повернуть вокруг X и вынести на середину фаски
            c.rotation_euler = (math.radians(45 * s), 0, 0)
            ym = s * (HG_HALF_W + 9.5) / 2
            zm = (RAIL_BASE + RAIL_BASE - (HG_HALF_W - 9.5)) / 2
            c.location = (0, ym * MM, zm * MM)
            apply_transform(c)
            boolean(hg, c)
    # нижние фаски — по треугольному окну между пазами (облегчение, как у Fab)
    for i, xc in enumerate(xs[:-1]):
        for s in (-1, 1):
            xm = xc - MLOK_PITCH / 2
            c = prism_xz(f"cut_low_tri{s}{i}", fillet([(xm - 6.0, -2.6), (xm + 6.0, -2.6), (xm, 3.2)], 1.2, 3), -6, 6, Hc)
            c.rotation_euler = (math.radians(-45 * s), 0, 0)
            ym = s * (HG_HALF_W + HG_HALF_W - 10.5) / 2
            zm = (-10.5 + HG_BOTTOM) / 2
            c.location = (0, ym * MM, zm * MM)
            apply_transform(c)
            boolean(hg, c)
    # гнёзда QD спереди по бокам
    for s in (-1, 1):
        y0, y1 = (HG_HALF_W - 7.0, HG_HALF_W + 3.0) if s > 0 else (-HG_HALF_W - 3.0, -HG_HALF_W + 7.0)
        boolean(hg, cyl(f"cut_qd{s}", y0, y1, 5.0, Hc, seg=32, cy=x1 - 8.0, cz=0.5, axis="Y"))
    finish(hg, w=0.45, seg=2, angle=35)
    o["handguard"] = hg
    o["mlok_x"] = xs
    # верхняя планка цевья: пазы в шаг с ресивером (центры x = 14 + 10·k)
    first = 14.0 + 10.0 * math.floor((x1 - 4.6 - 14.0) / 10.0)
    rl, slots = rail("Handguard_rail", x0 + 0.5, x1, Hc, slot_from=first)
    finish(rl, w=0.35, seg=2, angle=35)
    o["rail"] = rl
    # стяжные винты хомута (головки слева, гайки справа)
    for i, xs_ in enumerate((x0 + 9.0, x0 + 19.0)):
        scr = lathe(f"Handguard_screw{i}", [(-HG_HALF_W - 0.2, 0.0), (-HG_HALF_W - 0.2, 2.0), (HG_HALF_W - 1.4, 2.0), (HG_HALF_W - 1.4, 3.2),
                                            (HG_HALF_W - 0.3, 3.2), (HG_HALF_W, 2.8), (HG_HALF_W, 0.0)], Hc, "Steel_black", seg=24, cy=0, cz=0)
        scr.rotation_euler = (0, 0, math.pi / 2)
        apply_transform(scr)
        scr.location = (xs_ * MM, 0, -13.5 * MM)
        apply_transform(scr)
        hexa = prism_xz("cut_scr_hex", [(xs_ + 1.4 * math.cos(math.radians(60 * k)), -13.5 + 1.4 * math.sin(math.radians(60 * k))) for k in range(6)],
                        HG_HALF_W - 2.0, HG_HALF_W + 1, Hc)
        boolean(scr, hexa)
        auto_sharp(scr, 35)
        o[f"screw{i}"] = scr
    # гнёзда QD (втулки с кнопочным замком)
    for s in (-1, 1):
        qd = lathe("hg_qd", [(HG_HALF_W - 6.5, 0.0), (HG_HALF_W - 6.5, 5.0), (HG_HALF_W + 0.3, 5.0), (HG_HALF_W + 0.3, 3.9),
                             (HG_HALF_W - 4.0, 3.9), (HG_HALF_W - 4.0, 0.0)], Hc, "Steel_black", seg=32, cy=0, cz=0)
        qd.rotation_euler = (0, 0, math.pi / 2 if s > 0 else -math.pi / 2)
        apply_transform(qd)
        qd.location = ((x1 - 8.0) * MM, 0, 0.5 * MM)
        apply_transform(qd)
        qd.name = f"Handguard_QD_{'L' if s > 0 else 'R'}"
        auto_sharp(qd, 35)
        o[qd.name] = qd
    # упор для ладони снизу на переднем пазу
    o["handstop"] = handstop(Hc, xs[0])
    # короткая боковая планка слева на переднем пазу
    o["side_rail"] = side_rail(Hc, xs[0])
    return o


def handstop(Hc, xc):
    z0 = HG_BOTTOM
    prof = fillet([(xc - 20.0, z0), (xc + 18.0, z0), (xc + 18.0, z0 - 3.0), (xc + 9.0, z0 - 15.5), (xc + 4.0, z0 - 16.0),
                   (xc + 2.5, z0 - 13.0), (xc - 20.0, z0 - 3.2)], [1.0, 1.0, 2.5, 3.0, 2.5, 4.0, 2.0], 5)
    hs = prism_xz("Handstop", prof, -8.0, 8.0, Hc, "Polymer")
    # рёбра по бокам и облегчение
    for s in (-1, 1):
        boolean(hs, prism_xz(f"cut_hs_pocket{s}", fillet([(xc - 15.0, z0 - 1.3), (xc + 6.0, z0 - 1.3), (xc + 4.0, z0 - 2.6), (xc - 15.0, z0 - 2.6)], 0.5, 2),
                             6.6 * s, 9 * s, Hc))
    for xs in (xc - 10.0, xc + 10.0):
        boolean(hs, cyl("cut_hs_screw", z0 - 4, z0 + 1, 2.6, Hc, seg=20, cy=xs, cz=0, axis="Z"))
    finish(hs, w=0.5, seg=2, angle=35)
    for i, xs in enumerate((xc - 10.0, xc + 10.0)):
        sc = cyl(f"Handstop_screw{i}", z0 - 3.4, z0 + 0.5, 2.4, Hc, "Steel_black", seg=20, cy=xs, cz=0, axis="Z", ch=0.3)
        boolean(sc, prism_xy("cut_hs_hex", [(xs + 1.2 * math.cos(math.radians(60 * k)), 1.2 * math.sin(math.radians(60 * k))) for k in range(6)],
                             z0 - 5, z0 - 2.2, Hc))
        set_parent(sc, hs)
    return hs


def side_rail(Hc, xc):
    """Отрезок планки 1913 на левой грани (+Y): профиль планки повёрнут к стрелку боком."""
    L = 38.0
    r, _ = rail("Side_rail", xc - L / 2, xc + L / 2, Hc, slot_from=xc + 10.0, top=HG_HALF_W + 9.0, base=HG_HALF_W)
    # профиль rail строится в плоскости YZ вдоль z: поворачиваем на 90° вокруг X, чтобы «верх» смотрел в +Y
    r.rotation_euler = (math.radians(-90), 0, 0)
    apply_transform(r)
    # после поворота z→y: сдвигаем на середину боковой грани по высоте (z≈0.5)
    r.location = (0, 0, 0.5 * MM)
    apply_transform(r)
    finish(r, w=0.3, seg=2, angle=35)
    return r
