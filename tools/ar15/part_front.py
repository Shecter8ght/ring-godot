# AR-15: ствол 11.5″ с муфтой (боевые упоры), газовый блок и трубка, короткая гайка цевья, восьмигранное цевьё M-LOK
# с верхней планкой в линию ресивера, рядами треугольных окон на скошенных гранях и короткими планками 1913 на M-LOK
# спереди слева, справа и снизу.
import math
import bpy
from lib import (MM, UPPER_FRONT, RAIL_TOP, GAS_Z, BARREL_LEN, THREAD_X, BARREL_R_FRONT, GAS_BLOCK_X, HG_X, HG_HALF_W,
                 HG_BOTTOM, MLOK_PITCH, fillet, arc_pts, prism_xz, prism_yz, prism_xy, box, cyl, lathe, boolean, finish,
                 bevel_edges, auto_sharp, apply_transform, set_parent)
from part_upper import RAIL_BASE, FRONT_RING_LEN, rail, rail_profile

EXT_X = (-14.0, UPPER_FRONT + FRONT_RING_LEN + 2.0)   # муфта ствола: упоры сзади, фланец у торца кольца
NUT_X = (UPPER_FRONT + 0.2, 47.0)      # короткая гайка: на резьбовом кольце ресивера и чуть впереди — продолжение его трубы
BARREL_R_MID = 9.525                  # ствол под цевьём Ø0.75″ от муфты до газового блока (тонкий, как у образца)
CLAMP_X = (36.5, 43.5)                # стяжки хомута цевья: проходят в пазах гайки (держат от проворота)
BORE_R = 2.85
WALL = 2.6
HG_INNER_TOP = 20.6
MLOK_LEN, MLOK_H = 32.0, 7.0
HG_REAR_TAPER = 4.5           # длина конуса у заднего торца цевья
HG_REAR_INSET = 1.6           # насколько торец уже наружного восьмигранника


def _offset(poly, d):
    """Выпуклый многоугольник (y, z) против часовой, сдвинутый наружу на d (внутрь при d < 0)."""
    n = len(poly)
    lines = []
    for i in range(n):
        (y0, z0), (y1, z1) = poly[i], poly[(i + 1) % n]
        ln = math.hypot(y1 - y0, z1 - z0)
        ny, nz = (z1 - z0) / ln, -(y1 - y0) / ln
        lines.append(((y0 + ny * d, z0 + nz * d), (y1 - y0, z1 - z0)))
    out = []
    for i in range(n):
        (p, r), (q, s) = lines[i - 1], lines[i]
        den = r[0] * s[1] - r[1] * s[0]
        t = ((q[0] - p[0]) * s[1] - (q[1] - p[1]) * s[0]) / den
        out.append((p[0] + r[0] * t, p[1] + r[1] * t))
    return out


def rear_taper_cutter(C, x0):
    """Кольцевой резак конуса: наклонная поверхность от торца (внутрь на HG_REAR_INSET) до наружных граней."""
    import bmesh
    from lib import v as vmm
    prof = hg_outer()
    k = HG_REAR_INSET / HG_REAR_TAPER
    rings = [(x0 - 1.0, _offset(prof, -HG_REAR_INSET - k * 1.0)), (x0 + HG_REAR_TAPER + 0.5, _offset(prof, k * 0.5)),
             (x0 + HG_REAR_TAPER + 0.5, _offset(prof, 6.0)), (x0 - 1.0, _offset(prof, 6.0))]
    me = bpy.data.meshes.new("cut_hg_taper")
    bm = bmesh.new()
    vs = [[bm.verts.new(vmm(x, y, z)) for y, z in ring] for x, ring in rings]
    n = len(prof)
    for a, b in zip(vs, vs[1:] + vs[:1]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new("cut_hg_taper", me)
    C.objects.link(o)
    return o


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
    prof = [(EXT_X[1] - 4.0, BORE_R), (EXT_X[1] - 4.0, 10.4), (EXT_X[1] + 3.0, 10.4), (EXT_X[1] + 5.0, BARREL_R_MID),
            (gx1 + 1.0, BARREL_R_MID), (gx1 + 3.0, BARREL_R_FRONT),
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
    # гайка: сзади на резьбовом кольце ресивера (R 15.9), передняя стенка прижимает фланец муфты, спереди конус к стволу
    ring_end = UPPER_FRONT + FRONT_RING_LEN
    nut = lathe("Barrel_nut", [(NUT_X[0], 16.1), (NUT_X[0], 16.9), (NUT_X[0] + 0.6, 17.5), (NUT_X[1] - 7.0, 17.5),
                               (NUT_X[1] - 3.0, 15.6), (NUT_X[1], 12.6), (NUT_X[1], 10.9), (EXT_X[1] + 1.0, 10.9),
                               (EXT_X[1] + 1.0, 13.6), (ring_end + 0.2, 13.6), (ring_end + 0.2, 16.1)], Hc, "Steel_black", seg=72)
    boolean(nut, box("cut_nut_tube", NUT_X[0] - 1, NUT_X[1] + 1, -3.2, 3.2, 12.0, 20.0, Hc))
    # пазы под ключ на переднем конусе (кроме верха — там газовая трубка)
    for k in range(1, 8):
        a = 45.0 * k
        c = box("cut_nut_spline", NUT_X[1] - 7.5, NUT_X[1] + 1, -1.8, 1.8, 13.5, 19.0, Hc)
        c.rotation_euler = (math.radians(a), 0, 0)
        apply_transform(c)
        boolean(nut, c)
    # снизу сзади — выемка под проушину оси сборки ресивера (как вырез цевья над ней)
    boolean(nut, box("cut_nut_lug", NUT_X[0] - 1.0, 24.4, -7.6, 7.6, -25.0, -14.6, Hc))
    # поперечные пазы под стяжки хомута снизу
    for xs_ in CLAMP_X:
        boolean(nut, cyl("cut_nut_clamp", -30, 30, 2.3, Hc, seg=20, cy=xs_, cz=-13.5, axis="Y"))
    finish(nut, w=0.3, seg=2, angle=35)
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
    for xs in CLAMP_X:
        boolean(hg, cyl("cut_clamp", -30, 30, 2.1, Hc, seg=16, cy=xs, cz=-13.5, axis="Y"))
        boolean(hg, cyl("cut_clamp_cb", HG_HALF_W - 1.6, HG_HALF_W + 3, 3.4, Hc, seg=24, cy=xs, cz=-13.5, axis="Y"))
    # снизу сзади выемка под передок ресиверов (проушины оси сборки)
    boolean(hg, box("cut_receiver_notch", x0 - 1.0, x0 + 3.6, -16.6, 16.6, HG_BOTTOM - 3.0, -7.0, Hc))
    boolean(hg, box("cut_clamp_split", x0 - 1, CLAMP_X[1] + 6.0, -0.8, 0.8, HG_BOTTOM - 3, HG_BOTTOM + WALL + 0.5, Hc))
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
    # окна на скошенных гранях: ряды чередующихся треугольников (рёбра ~3 мм), сверху и снизу с обеих сторон
    for s_ in (-1, 1):
        boolean(hg, truss_cutter(f"cut_truss_top{s_}", Hc, 54.0, x1 - 10.0, 4.4, 12.0, 9.6, 45.0 * s_,
                                 s_ * (HG_HALF_W + 9.5) / 2, (RAIL_BASE + RAIL_BASE - (HG_HALF_W - 9.5)) / 2))
        boolean(hg, truss_cutter(f"cut_truss_low{s_}", Hc, 56.0, x1 - 16.0, 3.9, 10.0, 8.2, -45.0 * s_,
                                 s_ * (HG_HALF_W + HG_HALF_W - 10.5) / 2, (-10.5 + HG_BOTTOM) / 2))
    # гнёзда QD спереди по бокам
    for s in (-1, 1):
        y0, y1 = (HG_HALF_W - 7.0, HG_HALF_W + 3.0) if s > 0 else (-HG_HALF_W - 3.0, -HG_HALF_W + 7.0)
        boolean(hg, cyl(f"cut_qd{s}", y0, y1, 5.0, Hc, seg=32, cy=x1 - 8.0, cz=0.5, axis="Y"))
    # задний торец сходит на конус к ресиверу: все грани восьмигранника срезаны на HG_REAR_TAPER мм назад,
    # у торца — на HG_REAR_INSET мм внутрь (стык с ресивером без «коробки»)
    boolean(hg, rear_taper_cutter(Hc, x0))
    finish(hg, w=0.7, seg=3, angle=35)
    o["handguard"] = hg
    o["mlok_x"] = xs
    # верхняя планка цевья: пазы в шаг с ресивером (центры x = 14 + 10·k)
    first = 14.0 + 10.0 * math.floor((x1 - 4.6 - 14.0) / 10.0)
    rl, slots = rail("Handguard_rail", x0 + HG_REAR_TAPER + 1.0, x1, Hc, slot_from=first)
    finish(rl, w=0.35, seg=2, angle=35)
    o["rail"] = rl
    # стяжные винты хомута (головки слева, гайки справа)
    for i, xs_ in enumerate(CLAMP_X):
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
    # короткие планки 1913 на переднем пазу M-LOK: слева, справа и снизу (каждая на двух винтах с Т-гайками)
    for face, nm in (("L", "Side_rail"), ("R", "Side_rail_R"), ("B", "Bottom_rail")):
        o.update(mlok_rail(Hc, nm, xs[0] - 2.0, face))
    return o


def truss_cutter(name, C, xa, xb, h, base, step, angle, ym, zm):
    """Резак ряда треугольных окон на грани 45°: треугольники высотой 2h поперёк грани и основанием base вдоль неё,
    вершиной попеременно вверх и вниз через step — между ними наклонные рёбра; поворот на angle вокруг X и вынос
    на середину грани (ym, zm)."""
    from lib import join
    tris = []
    x = xa + base / 2
    k = 0
    while x + base / 2 <= xb:
        if k % 2 == 0:
            pts = [(x - base / 2, -h), (x + base / 2, -h), (x, h)]
        else:
            pts = [(x - base / 2, h), (x, -h), (x + base / 2, h)]
        tris.append(prism_xz(f"{name}_{k}", fillet(pts, 1.0, 3), -6, 6, C))
        x += step
        k += 1
    c = join(tris, name)
    c.rotation_euler = (math.radians(angle), 0, 0)
    c.location = (0, ym * MM, zm * MM)
    apply_transform(c)
    return c


def mlok_rail(Hc, name, xc, face):
    """Отрезок планки 1913 на пазу M-LOK: face — «L» (+Y), «R» (−Y), «B» (низ). Два винта с низкой головкой под
    шестигранник в площадках между пазами планки, внутри цевья — Т-гайки поперёк паза M-LOK."""
    o = {}
    L = 28.0
    base = (-HG_BOTTOM if face == "B" else HG_HALF_W) + 0.05      # на волос от грани — без совпадающих плоскостей
    top = base + 9.0
    r, _slots = rail(name, xc - L / 2, xc + L / 2, Hc, slot_from=xc + 5.0, top=top, base=base)
    parts = []
    for i, xx in enumerate((xc - 10.0, xc + 10.0)):
        boolean(r, cyl(f"cut_{name}_cb{i}", top - 1.9, top + 1.0, 2.95, Hc, seg=24, cy=xx, cz=0.0, axis="Z"))
        boolean(r, cyl(f"cut_{name}_hole{i}", base - 1.0, top, 1.65, Hc, seg=16, cy=xx, cz=0.0, axis="Z"))
        sc = cyl(f"{name}_screw{i}", base - WALL - 2.6, top - 1.8, 1.5, Hc, "Steel_black", seg=16, cy=xx, cz=0.0, axis="Z")
        boolean(sc, cyl(f"{name}_head{i}", top - 1.8, top - 0.3, 2.7, Hc, "Steel_black", seg=24, cy=xx, cz=0.0, axis="Z", ch=0.3), "UNION")
        boolean(sc, prism_xy(f"cut_{name}_hex{i}", [(xx + 1.25 * math.cos(math.radians(60 * k)), 1.25 * math.sin(math.radians(60 * k)))
                                                     for k in range(6)], top - 1.4, top + 1.0, Hc))
        finish(sc, w=0.15, seg=2, angle=35)
        nut = box(f"{name}_tnut{i}", xx - 3.2, xx + 3.2, -5.2, 5.2, base - WALL - 2.9, base - WALL - 0.1, Hc, "Steel_black")
        boolean(nut, cyl(f"cut_{name}_tn{i}", base - WALL - 4, base - WALL + 1, 1.55, Hc, seg=16, cy=xx, cz=0.0, axis="Z"))
        finish(nut, w=0.3, seg=2, angle=35)
        parts += [sc, nut]
    finish(r, w=0.3, seg=2, angle=35)
    # строили «верхом вверх» (+Z): разворачиваем к своей грани и ставим на середину паза M-LOK по высоте
    ang = {"L": -90.0, "R": 90.0, "B": 180.0}[face]
    dz = 0.0 if face == "B" else 0.5
    for ob in [r] + parts:
        ob.rotation_euler = (math.radians(ang), 0, 0)
        apply_transform(ob)
        ob.location = (0, 0, dz * MM)
        apply_transform(ob)
    o[name] = r
    for ob in parts:
        o[ob.name] = ob
    return o
