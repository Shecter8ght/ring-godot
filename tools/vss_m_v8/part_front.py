# ВСС-М v8: цевьё (ВСС-М: полимер с поперечными рёбрами сверху), ствол с отверстиями под глушитель,
# съёмный глушитель (задняя муфта, корпус с насечкой, передняя крышка, перегородки, сквозной канал),
# секторный прицел на глушителе (откидной лист, хомутик, шарнир спереди), мушка с намушником,
# съёмная муфта с планками Пикатинни на 3, 6 и 9 часов (ВСС-М).
import math
from mathutils import Matrix
from lib import (BORE_Z, MM, apply_transform, auto_sharp, box, boolean, cyl, fillet, finish, join, lathe, loft_yz,
                 prism_xz, prism_yz, material)
from part_receiver import picatinny

HG_X0, HG_X1 = 478.2, 567.0
SUP_X0, SUP_X1 = 567.3, 894.0
SLEEVE_X0, SLEEVE_X1 = 570.6, 662.0
SIGHT_DZ = 12.1          # подъём целика и мушки: линия прицеливания выше цевья (49) и планки крышки (51.2)


def rounded_section(top, bot, w_top, w_mid, w_bot, z_mid, n=12):
    """Сечение цевья: верхняя дуга, бока, сужение книзу. Возвращает список (y, z) по контуру с равным числом точек."""
    pts = [(-w_bot, bot), (w_bot, bot), (w_mid, z_mid), (w_top, top - 6.0), (w_top - 6.0, top), (-(w_top - 6.0), top),
           (-w_top, top - 6.0), (-w_mid, z_mid)]
    return fillet(pts, [6.0, 6.0, 14.0, 6.0, 6.0, 6.0, 6.0, 14.0], n)


def build(ctx):
    Cf = ctx["coll"]["Front"]
    Cs = ctx["coll"]["Suppressor"]
    Cr = ctx["coll"]["Rail_sleeve"]
    out = {}

    # --- цевьё ---
    secs = []
    xs = [HG_X0, HG_X0 + 1.2, 500.0, 530.0, 556.0, 562.5, 565.5, HG_X1]
    for x in xs:
        t = (x - HG_X0) / (HG_X1 - HG_X0)
        bot = -26.0 + 9.0 * t
        s = 1.0
        if x == HG_X0:
            s = 0.965
        elif x > 560:
            s = 1.0 - ((x - 560.0) / 7.0) ** 2 * 0.07
        sec = rounded_section(48.0, bot, 19.5, 24.2, 15.5, 16.0)
        cz = 16.0
        secs.append((x, [(y * s, cz + (z - cz) * s) for y, z in sec]))
    hg = loft_yz("Handguard", secs, Cf, "Polymer_handguard")
    boolean(hg, cyl("_hgb", 560, 580, 9.6, Cf, seg=48))                               # проход ствола
    boolean(hg, cyl("_hgr", 565.8, 580, 22.6, Cf, seg=64))                            # гнездо задней муфты глушителя
    # поперечные рёбра по верху (ВСС-М): мелкие, часто
    ribs = []
    top_pts = [p for p in rounded_section(48.0, -20.0, 19.5, 24.2, 15.5, 16.0) if p[1] > 37.0]
    top_pts.sort(key=lambda p: math.atan2(p[1] - 16.0, p[0]))
    for i in range(18):
        xc = 485.0 + i * 4.2
        outer = [(y * 1.021, 16.0 + (z - 16.0) * 1.021) for y, z in top_pts]
        inner = [(y * 0.99, 16.0 + (z - 16.0) * 0.99) for y, z in reversed(top_pts)]
        ribs.append(prism_yz(f"_rib{i}", outer + inner, xc - 0.7, xc + 0.7, Cf))
    rj = join(ribs, "_ribs")
    boolean(hg, rj, op="UNION")
    finish(hg, 1.4, 3, 35)
    out["handguard"] = hg
    # передний антабок слева: проушина на цевье и поворотная скоба
    lug = prism_xz("Front_sling_bracket", fillet([(556.0, 2.0), (565.0, 2.0), (565.0, 12.0), (556.0, 12.0)], 2.0, 3), 22.0, 25.6, Cf, "Steel_black")
    boolean(lug, cyl("_slh", 20, 28, 1.6, Cf, axis="Y", cy=560.5, cz=7.0, seg=20))
    finish(lug, 0.4, 2, 35)
    loop_pts = fillet([(553.0, -12.0), (568.0, -12.0), (568.0, 6.5), (553.0, 6.5)], 5.0, 6)
    ring_o = [(x, z) for x, z in loop_pts]
    import bpy as _b
    cu = _b.data.curves.new("Front_sling_swivel", "CURVE"); cu.dimensions = "3D"
    sp = cu.splines.new("POLY"); sp.points.add(len(ring_o) - 1)
    for k, (x, z) in enumerate(ring_o):
        sp.points[k].co = (x * MM, 26.6 * MM, z * MM, 1.0)
    sp.use_cyclic_u = True
    cu.bevel_depth = 1.3 * MM; cu.bevel_resolution = 3
    so = _b.data.objects.new("_swc", cu); Cf.objects.link(so)
    dg = _b.context.evaluated_depsgraph_get()
    me = _b.data.meshes.new_from_object(so.evaluated_get(dg), depsgraph=dg)
    _b.data.objects.remove(so, do_unlink=True); _b.data.curves.remove(cu)
    sw = _b.data.objects.new("Front_sling_swivel", me); Cf.objects.link(sw)
    me.materials.append(material("Steel_black"))
    for p_ in me.polygons:
        p_.use_smooth = True
    out["swivel"] = sw
    out["swivel_lug"] = lug

    # --- ствол с рядами отверстий ---
    barrel = lathe("Barrel", [(478.0, 4.62), (478.0, 9.0), (560.0, 9.0), (561.0, 8.2), (675.3, 8.2), (676.0, 7.5), (676.0, 4.62)],
                   Cf, "Steel_black", 48)
    holes = []
    for row in range(6):
        for k in range(8):
            x = 592.0 + k * 10.0 + (5.0 if row % 2 else 0.0)
            if x > 668:
                continue
            a = math.radians(60 * row + 30)
            h = cyl(f"_bh{row}_{k}", -1.0, 12.0, 1.5, Cf, axis="Z", cy=0.0, cz=0.0, seg=16)
            h.data.transform(Matrix.Rotation(a, 4, "X"))
            h.data.transform(Matrix.Translation((x * MM, 0, BORE_Z * MM)))
            holes.append(h)
    boolean(barrel, join(holes, "_bholes"))
    auto_sharp(barrel, 35)
    out["barrel"] = barrel

    # --- глушитель (съёмный) ---
    prof = [(SUP_X0, 9.05), (SUP_X0, 21.4), (568.1, 22.0), (581.0, 22.0), (581.8, 21.3), (582.6, 19.6),
            (649.2, 19.6), (650.0, 20.3), (667.0, 20.3), (667.8, 19.6), (699.2, 19.6), (700.0, 20.0),
            (851.0, 20.0), (851.8, 20.6), (857.0, 20.6), (857.2, 20.1), (858.8, 20.1), (859.0, 20.6),
            (866.0, 20.6), (866.2, 20.1), (867.8, 20.1), (868.0, 20.6), (892.6, 20.6), (894.0, 19.4),
            (SUP_X1, 7.4), (893.3, 6.2), (893.0, 5.25), (888.5, 5.25), (888.5, 18.3), (585.6, 18.3),
            (584.6, 17.4), (583.4, 9.05)]
    sup = lathe("Suppressor_body", prof, Cs, "Steel_black", 72)
    auto_sharp(sup, 28)
    # перегородки с отверстием по оси (канал сквозной)
    baf = []
    for i, x in enumerate(range(690, 886, 21)):
        b = lathe(f"_baf{i}", [(x, 5.6), (x, 18.3), (x + 1.4, 18.3), (x + 7.5, 7.0), (x + 7.5, 5.6)], Cs, None, 48)
        baf.append(b)
    baffles = join(baf, "Suppressor_baffles")
    baffles.data.materials.clear(); baffles.data.materials.append(material("Steel_black"))
    auto_sharp(baffles, 30)
    out["suppressor"] = sup
    out["baffles"] = baffles

    # --- прицел поднят над цевьём и планкой крышки: линия прорезь — мушка проходит выше них (замечание владельца) ---
    # основание приварено к глушителю (седло), на нём стойка; сектор и шарнир листа — на стойке
    DZ = SIGHT_DZ
    def saddle(name, x0, x1, top, half_w, coll):
        sec = [(-half_w, 25.0), (half_w, 25.0), (half_w, top), (-half_w, top)]
        o = prism_yz(name, fillet(sec, [0, 0, 1.0, 1.0], 3), x0, x1, coll, "Steel_black")
        boolean(o, cyl("_sad", x0 - 1, x1 + 1, 19.5, coll, seg=72))
        return o
    base = saddle("Rear_sight_base", 586.0, 646.0, 33.2, 6.2, Cs)
    riser = prism_xz("_riser", fillet([(587.0, 32.5), (646.0, 32.5), (646.0, 33.0 + DZ), (587.0, 33.0 + DZ)], [0, 0, 1.5, 1.5], 3),
                     -5.4, 5.4, Cs)
    ramp_pts = [(589.0, 32.5 + DZ)] + [(590.0 + 36.0 * t / 10, 34.3 + DZ + 1.0 * ((36.0 * t / 10) / 30.0) ** 2) for t in range(11)] + [(627.0, 32.5 + DZ)]
    ramp = prism_xz("_ramp", ramp_pts, -3.4, 3.4, Cs)
    # колодка шарнира — ниже линии прицеливания (иначе закрывает мушку)
    tower = prism_xz("_tower", fillet([(627.0, 32.5), (646.0, 32.5), (646.0, 37.0 + DZ), (641.0, 40.0 + DZ), (627.0, 40.0 + DZ)],
                                      [0, 0, 3.0, 2.5, 1.0], 4), -6.2, 6.2, Cs)
    boolean(base, join([riser, ramp, tower], "_rt"), op="UNION", self_x=True)
    boolean(base, box("_lw", 626.5, 640.0, -3.6, 3.6, 35.0 + DZ, 50.0 + DZ, Cs))       # гнездо листа
    boolean(base, cyl("_hp", -8, 8, 1.1, Cs, axis="Y", cy=633.0, cz=39.5 + DZ, seg=16))
    # облегчающие выборки по бокам стойки
    for s in (-1, 1):
        boolean(base, prism_xz(f"_rp{s}", fillet([(592.0, 35.5), (622.0, 35.5), (622.0, 31.0 + DZ), (592.0, 31.0 + DZ)], 2.0, 3),
                               s * 4.6, s * 8.0, Cs))
    finish(base, 0.6, 3, 35)
    pin = cyl("Rear_sight_hinge_pin", -6.6, 6.6, 1.05, Cs, axis="Y", cy=633.0, cz=39.5 + DZ, seg=16)
    weld = []
    for s in (-1, 1):
        for k in range(25):
            x = 587.5 + k * 2.4
            b = lathe(f"_w{s}_{k}", [(0, 0), (0, 1.0), (0.5, 0.85), (0.9, 0.4), (1.0, 0)], Cs, None, 10, 0, 0)
            b.rotation_euler = (0, 0, math.pi / 2 * s)
            b.location = (x * MM, s * 6.15 * MM, 26.6 * MM)
            apply_transform(b)
            weld.append(b)
    wj = join(weld, "Rear_sight_weld")
    wj.data.materials.clear(); wj.data.materials.append(material("Steel_black"))
    out["sight_base"] = base

    # лист прицела: шарнир спереди, целик сзади
    leaf = prism_xz("Rear_sight_leaf", fillet([(579.0, 36.5 + DZ), (636.0, 37.2 + DZ), (636.0, 41.6 + DZ), (630.0, 38.1 + DZ), (579.0, 38.1 + DZ)],
                                              [0.5, 1.5, 1.5, 0.5, 0.5], 3), -3.2, 3.2, Cs, "Steel_black")
    notch = prism_xz("_notch", fillet([(578.0, 36.0 + DZ), (581.0, 36.0 + DZ), (581.0, 44.2 + DZ), (578.0, 44.2 + DZ)], [0.3, 0.3, 0.8, 0.8], 3),
                     -4.2, 4.2, Cs)
    boolean(leaf, notch, op="UNION")
    boolean(leaf, prism_yz("_u", fillet([(-0.85, 42.2 + DZ), (0.85, 42.2 + DZ), (0.85, 46.5 + DZ), (-0.85, 46.5 + DZ)], [0.85, 0.85, 0, 0], 4),
                           577, 582, Cs))
    boolean(leaf, cyl("_lp", -5, 5, 1.1, Cs, axis="Y", cy=633.0, cz=39.5 + DZ, seg=16))
    from part_stamps import stamp
    for i, x in enumerate((590.5, 600.0, 609.5, 619.0)):
        stamp(leaf, str(i + 1), 2.4, (x, 0.0, 38.1 + DZ), (0, 0, 1), (1, 0, 0), 0.1, Cs)
    finish(leaf, 0.3, 2, 35)
    slider = prism_yz("Rear_sight_slider", fillet([(-5.2, 34.6 + DZ), (5.2, 34.6 + DZ), (5.2, 40.2 + DZ), (-5.2, 40.2 + DZ)], 1.0, 3),
                      588.0, 596.0, Cs, "Steel_black")
    boolean(slider, box("_sl", 586, 598, -3.3, 3.3, 36.4 + DZ, 38.2 + DZ, Cs))
    for s in (-1, 1):
        btn = cyl(f"_btn{s}", s * 5.0, s * 8.4, 3.0, Cs, axis="Y", cy=592.0, cz=37.4 + DZ, seg=32, ch=0.4)
        boolean(slider, btn, op="UNION")
    finish(slider, 0.5, 2, 35)
    out["leaf"] = leaf
    out["slider"] = slider

    # --- мушка с намушником: на стойке, вершина мушки чуть выше дна прорези ---
    fbase = saddle("Front_sight_base", 873.0, 886.0, 36.5, 7.0, Cs)
    fr = prism_xz("_friser", fillet([(874.0, 35.0), (885.0, 35.0), (885.0, 44.0 + DZ - 10.6), (874.0, 44.0 + DZ - 10.6)], [0, 0, 1.0, 1.0], 3),
                  -4.6, 4.6, Cs)
    boolean(fbase, fr, op="UNION", self_x=True)
    ears = []
    for s in (-1, 1):
        e = prism_xz(f"_ear{s}", fillet([(873.0, 30.0), (886.0, 30.0), (885.0, 50.0 + DZ + 0.5), (874.0, 50.0 + DZ + 0.5)], [0, 0, 2.5, 2.5], 4),
                     s * 4.8, s * 6.8, Cs)
        ears.append(e)
    boolean(fbase, join(ears, "_ears"), op="UNION", self_x=True)
    boolean(fbase, cyl("_eh", -9, 9, 2.0, Cs, axis="Y", cy=879.5, cz=44.0 + DZ, seg=24))
    finish(fbase, 0.6, 3, 35)
    post_base = 44.0 + DZ - 10.6
    post_top = 42.2 + DZ + 0.6          # чуть выше дна прорези целика (пристрелка)
    L = post_top - post_base
    post = lathe("Front_sight_post", [(0, 0), (0, 2.6), (3.0, 2.6), (3.0, 1.1), (L, 1.1), (L, 0)], Cs, "Steel_black", 24, 0, 0)
    post.rotation_euler = (0, -math.pi / 2, 0)
    post.location = (879.5 * MM, 0, post_base * MM)
    apply_transform(post)
    auto_sharp(post, 35)
    out["front_sight"] = fbase

    # --- муфта с планками (ВСС-М, съёмная) ---
    half = 23.2
    c = 7.0
    octo = [(-half + c, -half + BORE_Z), (half - c, -half + BORE_Z), (half, -half + c + BORE_Z), (half, half - c + BORE_Z),
            (half - c, half + BORE_Z), (-half + c, half + BORE_Z), (-half, half - c + BORE_Z), (-half, -half + c + BORE_Z)]
    sl = prism_yz("Rail_sleeve", fillet(octo, 1.2, 2), SLEEVE_X0, SLEEVE_X1, Cr, "Alu_anodized")
    boolean(sl, cyl("_sb", SLEEVE_X0 - 1, SLEEVE_X1 + 1, 19.85, Cr, seg=72))
    boolean(sl, cyl("_sbc", SLEEVE_X0 - 1, 582.6, 22.25, Cr, seg=72))
    boolean(sl, box("_stop", 583.5, 648.5, -7.2, 7.2, 20.0, 40.0, Cr))               # окно под прицел
    # облегчающие отверстия на скосах
    hs = []
    for q in range(4):
        a = math.radians(45 + 90 * q)
        for k in range(7):
            x = 586.0 + k * 10.5
            h = cyl(f"_sh{q}_{k}", 14.0, 30.0, 2.6, Cr, axis="Z", cy=0, cz=0, seg=20)
            h.data.transform(Matrix.Rotation(a, 4, "X"))
            h.data.transform(Matrix.Translation((x * MM, 0, BORE_Z * MM)))
            hs.append(h)
    boolean(sl, join(hs, "_shs"))
    # прорезь стяжки снизу слева и винты
    finish(sl, 0.8, 3, 35)
    rails = []
    for ang in (90, -90, 180):
        r, _ = picatinny(f"_sr{ang}", 574.0, 658.5, BORE_Z + half - 0.2, Cr, "Alu_anodized")
        r.data.transform(Matrix.Translation((0, 0, -BORE_Z * MM)))
        r.data.transform(Matrix.Rotation(math.radians(ang), 4, "X"))
        r.data.transform(Matrix.Translation((0, 0, BORE_Z * MM)))
        rails.append(r)
    out["sleeve"] = join([sl] + rails, "Rail_sleeve")
    screws = []
    for q in (0, 3):
        a = math.radians(45 + 90 * q)
        for x in (575.5, 656.5):
            sc_ = lathe(f"_scr{q}_{x}", [(0, 0), (0, 2.9), (0.5, 2.9), (2.3, 2.6), (2.5, 0)], Cr, None, 24, 0, 0)
            sc_.rotation_euler = (0, -math.pi / 2, 0)
            apply_transform(sc_)
            boolean(sc_, prism_xy_hex(f"_hex{q}{x}", 1.25, 1.2, 3.0, Cr))
            sc_.data.transform(Matrix.Translation((0, 0, ((2 * half - c) / math.sqrt(2) - 0.25) * MM)))
            sc_.data.transform(Matrix.Rotation(a, 4, "X"))
            sc_.data.transform(Matrix.Translation((x * MM, 0, BORE_Z * MM)))
            screws.append(sc_)
    sj = join(screws, "Rail_sleeve_screws")
    sj.data.materials.clear(); sj.data.materials.append(material("Steel_black"))
    auto_sharp(sj, 35)
    return out


def prism_xy_hex(name, r, z0, z1, coll):
    from lib import prism_xy
    pts = [(r * math.cos(math.radians(60 * k)), r * math.sin(math.radians(60 * k))) for k in range(6)]
    return prism_xy(name, pts, z0, z1, coll)
