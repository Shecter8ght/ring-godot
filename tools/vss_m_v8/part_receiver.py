# ВСС-М v8: ствольная коробка, крышка с планкой Пикатинни, боковая планка «ласточкин хвост», спусковая скоба.
# Размеры сняты с профильного фото ВСС (масштаб по длине 894 мм) и с фото ВСС-М (В. Кузьмин, CC BY-SA 4.0);
# ось канала z=10, торец затыльника x=0, правая сторона −Y.
import math
from lib import (BORE_Z, LOWER_W, COVER_W, CAV_W, box, boolean, cyl, fillet, finish, join, lathe, loft_yz, prism_xz, prism_yz, prism_xy, set_origin,
                 auto_sharp, material, apply_all, bevel_edges)

TOP_Z = 8.0             # плоскость разъёма коробка/крышка
COVER_TOP = 42.0
COVER_REAR_Z = 11.3                      # низ крышки сзади — над гребнем приклада
COVER_SLOPE_X0, COVER_SLOPE_X1 = 272.0, 298.0   # скос заднего торца крышки (замечание владельца 25.10)
WIN_X0, WIN_X1 = 405.0, 475.5   # окно затворной рамы справа
WIN_Z0, WIN_Z1 = 2.0, 30.0
WELL_X0, WELL_X1 = 412.5, 478.5  # шахта магазина
WELL_W = 16.5


def picatinny(name, x0, x1, base_z, coll, mat, n_slots=None, pitch=10.01, slot_w=5.23):
    """Планка MIL-STD-1913: гребень с 45° скосами, поперечные пазы; основание — на высоте base_z."""
    h_top = 9.4
    half = [(7.4, 0.0), (7.4, 2.4), (10.6, 5.6), (10.6, 6.6), (7.8, h_top)]
    pts = [(-y, z) for y, z in reversed(half)] + [(y, z) for y, z in half]
    sec = [(y, base_z + z) for y, z in fillet(pts, [0, 0.3, 0.25, 0.3, 0.6, 0.6, 0.3, 0.25, 0.3, 0], 2)]
    rail = prism_yz(name, sec, x0, x1, coll, mat)
    L = x1 - x0
    if n_slots is None:
        n_slots = int((L - 6.0) // pitch) + 1
    start = x0 + (L - (n_slots - 1) * pitch) / 2.0
    cutters = []
    for i in range(n_slots):
        cx = start + i * pitch
        cutters.append(box(f"_slot{i}", cx - slot_w / 2, cx + slot_w / 2, -15, 15, base_z + 6.4, base_z + 20, coll))
    cut = join(cutters, "_slots")
    boolean(rail, cut)
    # торцы планки со скосом
    finish(rail, 0.45, 2, 40)
    return rail, [start + i * pitch for i in range(n_slots)]


def _rsec(top, bottom, w, rt, rb, seg=8):
    """Сечение крышки: прямоугольник ±w × [bottom, top], верхние углы радиуса rt, нижние rb; число точек постоянно."""
    h = top - bottom
    rt = max(0.05, min(rt, h * 0.48, w * 0.9))
    rb = max(0.05, min(rb, h * 0.3))
    pts = []
    for cx, cz, r, a0 in ((w - rb, bottom + rb, rb, -90.0), (w - rt, top - rt, rt, 0.0),
                          (-w + rt, top - rt, rt, 90.0), (-w + rb, bottom + rb, rb, 180.0)):
        for k in range(seg + 1):
            a = math.radians(a0 + 90.0 * k / seg)
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return pts


def cover_loft(C):
    """Крышка лофтом: задний торец скошен (~50°) и скруглён, рёбра скоса со сторонами — радиусом верхних углов
    сечения (замечание владельца 25.10: «скошенной и с более круглыми углами»)."""
    line = fillet([(240.0, COVER_REAR_Z), (COVER_SLOPE_X0, COVER_REAR_Z), (COVER_SLOPE_X1, COVER_TOP), (340.0, COVER_TOP)],
                  [0, 3.0, 16.0, 0], 14)

    def top(x):
        for (x0, z0), (x1, z1) in zip(line, line[1:]):
            if x0 <= x <= x1 and x1 > x0:
                return z0 + (z1 - z0) * (x - x0) / (x1 - x0)
        return COVER_TOP if x > line[-1][0] else COVER_REAR_Z
    xs = []
    x = COVER_SLOPE_X0
    while top(x) - COVER_REAR_Z < 1.0:
        x += 0.2
    while x < 312.0:
        xs.append(round(x, 3))
        x += 0.8 if x < 300.0 else 1.6
    xs += [478.0]
    secs = []
    for x in xs:
        b = COVER_REAR_Z if x < 282.6 else TOP_Z - 1.0
        if 282.0 < x < 283.3:
            continue
        secs.append((x, _rsec(top(x), b, COVER_W, 6.5, 0.6)))
    # ступенька низа у заднего торца коробки: два сечения рядом
    secs.append((282.55, _rsec(top(282.55), COVER_REAR_Z, COVER_W, 6.5, 0.6)))
    secs.append((282.65, _rsec(top(282.65), TOP_Z - 1.0, COVER_W, 6.5, 0.6)))
    secs.sort(key=lambda t: t[0])
    return loft_yz("Receiver_cover", secs, C, "Steel_black", cap=True, smooth=True)


def build(ctx):
    C = ctx["coll"]["Receiver"]
    out = {}

    # --- нижняя коробка: профиль сбоку (x, z) ---
    prof = [
        (282.0, TOP_Z), (478.0, TOP_Z), (478.0, -17.0),      # передний торец
        (413.0, -44.5), (406.5, -44.5),                      # скошенный низ шахты
        (404.0, -14.0), (358.0, -14.0),                      # верх окна под спуск
        (357.5, -36.0), (347.0, -36.0),                      # прилив переводчика за спуском
        (346.0, -25.2), (282.0, -25.2),                      # опора на приклад
    ]
    r = [0.8, 1.2, 3.0, 4.0, 2.0, 1.0, 1.5, 1.5, 1.5, 1.0, 0.8]
    lower = prism_xz("Receiver_lower", fillet(prof, r, 4), -LOWER_W, LOWER_W, C, "Steel_black")
    # полость затворной рамы (открыта сверху), шахта, окно справа, отверстие под ствол
    boolean(lower, box("_cav", 285.0, 468.0, -CAV_W, CAV_W, -12.0, 20.0, C))
    boolean(lower, box("_well", WELL_X0, WELL_X1, -WELL_W, WELL_W, -60.0, -7.0, C))
    boolean(lower, box("_win", WIN_X0, WIN_X1, -30.0, -13.5, WIN_Z0, 20.0, C))
    # паз хода рукоятки взведения вдоль окна (рукоятка идёт назад до 74 мм)
    boolean(lower, box("_hslot", 385.0, WIN_X0 + 1.0, -30.0, -13.5, 3.5, 20.0, C))
    # шов «коробка — корпус УСМ» и фрезерованные выборки по бокам
    for s in (-1, 1):
        y_out = s * (LOWER_W + 1.0)
        seam = prism_xz(f"_seam{s}", [(284.0, -13.6), (357.0, -13.6), (357.0, -13.0), (284.0, -13.0)],
                        s * (LOWER_W - 0.35), y_out, C)
        boolean(lower, seam)
        pocket = prism_xz(f"_pock{s}", fillet([(292.0, -22.0), (340.0, -22.0), (340.0, -15.5), (292.0, -15.5)], 2.0, 3),
                          s * (LOWER_W - 0.6), y_out, C)
        boolean(lower, pocket)
        wellp = prism_xz(f"_wellp{s}", fillet([(418.0, -38.0), (472.0, -17.0), (472.0, -3.0), (418.0, -3.0)], [3, 3, 3, 3], 3),
                         s * (LOWER_W - 0.5), y_out, C)
        boolean(lower, wellp)
    # прорезь под перо спуска в дне коробки
    boolean(lower, box("_tslot", 364.5, 385.5, -3.3, 3.3, -16.0, -6.0, C))
    # паз защёлки магазина и проход её зуба в шахту
    boolean(lower, box("_catch", 405.0, 411.6, -7.6, 7.6, -60.0, -27.0, C))
    boolean(lower, box("_catcht", 411.0, 414.0, -3.9, 3.9, -31.5, -27.0, C))
    # канал подачи патрона к патроннику и гнездо переднего зацепа магазина
    boolean(lower, box("_feed", 466.0, 479.0, -6.6, 6.6, -8.0, 9.0, C))
    boolean(lower, box("_flugr", 475.5, 479.0, -9.4, 9.4, -11.5, -4.5, C))
    # отверстие под переводчик (поперечное) и под ось защёлки
    boolean(lower, cyl("_selh", -30, 30, 3.0, C, axis="Y", cy=352.0, cz=-29.5, seg=24))
    from part_stamps import stamp, SERIAL, SUB
    stamp(lower, SERIAL, 3.6, (446.0, -(LOWER_W - 0.5), -8.6), (0, -1, 0), (0, 0, 1), 0.15, C)
    stamp(lower, "2019", 2.6, (446.0, LOWER_W - 0.5, -8.6), (0, 1, 0), (0, 0, 1), 0.12, C)
    finish(lower, 0.9, 3, 35)
    out["lower"] = lower

    # --- вкладыш ствола (казённик): видно в окне при отведённой раме ---
    # сзади шесть каналов под упоры (в отпертом положении упоры на 30°+60°k), за ними кольцевая выточка запирания,
    # впереди патронник; зеркало затвора в запертом положении x=474.5
    trun = prism_yz("Receiver_trunnion", fillet([(-CAV_W, -6.0), (CAV_W, -6.0), (CAV_W, 20.0), (-CAV_W, 20.0)], 1.0, 2),
                    465.5, 478.0, C, "Steel_black")
    boolean(trun, cyl("_tb", 460, 474.6, 7.05, C, seg=48))
    boolean(trun, cyl("_ch", 474.0, 480, 5.95, C, seg=48))
    boolean(trun, cyl("_lockgroove", 469.6, 474.4, 9.9, C, seg=48))
    lugs = []
    from mathutils import Matrix as _M
    for k in range(6):
        a = math.radians(30 + 60 * k)
        o = box(f"_lug{k}", 465.0, 470.0, -2.5, 2.5, 0.0, 9.9, C)
        o.data.transform(_M.Rotation(a, 4, "X"))
        o.data.transform(_M.Translation((0, 0, BORE_Z * 0.001)))
        lugs.append(o)
    boolean(trun, join(lugs, "_lugs"))
    # скат подачи патрона снизу
    boolean(trun, prism_yz("_ramp", [(-6, -7), (6, -7), (4.2, 4.6), (-4.2, 4.6)], 465.0, 476.0, C))
    finish(trun, 0.5, 2, 35)
    out["trunnion"] = trun

    # --- крышка ствольной коробки ВСС-М ---
    cover = cover_loft(C)
    # внутренняя полость повторяет скос со стенкой ~2.5 мм; рама при полном отводе (торец x=286) проходит под ним
    inner = fillet([(480.0, TOP_Z - 1.5), (284.6, TOP_Z - 1.5), (284.6, 22.4), (298.8, COVER_TOP - 3.0), (480.0, COVER_TOP - 3.0)],
                   [0, 0, 1.0, 11.5, 0], 8)
    boolean(cover, prism_xz("_cin", inner, -(COVER_W - 2.2), COVER_W - 2.2, C))
    boolean(cover, box("_cwin", WIN_X0, 480.0, -30.0, -(COVER_W - 3.0), TOP_Z - 1.0, WIN_Z1, C))
    for s in (-1, 1):
        band = prism_yz(f"_band{s}", [(s * (COVER_W - 0.7), 30.0), (s * 30, 30.0), (s * 30, 39.0), (s * (COVER_W - 0.7), 39.0)],
                        304.0, 472.0, C)
        boolean(cover, band)
    boolean(cover, box("_chs", 385.0, WIN_X0 + 1.0, -30.0, -(COVER_W - 3.0), TOP_Z - 1.0, 10.5, C))
    boolean(cover, cyl("_lh", 270, 296, 3.6, C, cz=28.0, seg=32))
    stamp(cover, SUB, 2.4, (318.0, -COVER_W, 21.0), (0, -1, 0), (0, 0, 1), 0.12, C)
    auto_sharp(cover, 40)
    finish(cover, 0.8, 3, 40)
    rail, slots = picatinny("Cover_picatinny", 307.0, 472.5, COVER_TOP - 0.2, C, "Steel_black")
    out["cover"] = cover
    out["rail"] = rail
    out["rail_slots"] = slots

    # фиксатор крышки — задний упор направляющей возвратной пружины
    latch = lathe("Cover_latch_button", [(281.4, 0.0), (281.4, 2.5), (282.2, 3.2), (290.0, 3.2), (290.0, 4.6), (292.0, 4.6), (292.0, 0.0)],
                  C, "Steel_black", 32, 0.0, 28.0)
    auto_sharp(latch, 30)
    out["latch"] = latch

    # --- боковая планка «ласточкин хвост» под ПСО (слева, +Y) ---
    plate = prism_xz("Side_mount_plate", fillet([(307.0, -10.0), (415.0, -10.0), (415.0, 3.0), (307.0, 3.0)], 1.5, 3),
                     LOWER_W - 0.2, LOWER_W + 2.2, C, "Steel_black")
    finish(plate, 0.7, 3, 35)
    dov = prism_yz("Side_mount_dovetail", [(LOWER_W + 2.1, -6.8), (LOWER_W + 2.1, -0.4), (LOWER_W + 5.6, 1.2), (LOWER_W + 5.6, -8.4)],
                   310.0, 412.0, C, "Steel_black")
    boolean(dov, box("_stop", 357.0, 360.5, LOWER_W + 3.8, 30, -10, 5, C))
    finish(dov, 0.5, 2, 35)
    out["mount"] = join([plate, dov], "Side_mount_dovetail")
    for i, x in enumerate((316.0, 361.0, 406.0)):
        rv = lathe(f"Side_mount_rivet_{i}", [(0, 0), (0, 2.1), (0.5, 2.0), (0.9, 1.4), (1.1, 0.0)], C, "Steel_black", 24, 0, 0)
        rv.rotation_euler = (0, 0, math.pi / 2)
        rv.location = (x * 0.001, (LOWER_W + 2.2) * 0.001, -3.5 * 0.001)
        from lib import apply_transform
        apply_transform(rv)
        auto_sharp(rv, 40)

    # --- спусковая скоба ---
    outer = fillet([(346.6, -14.2), (358.5, -14.2), (358.5, -24.0), (401.0, -24.0), (401.0, -14.2), (405.0, -14.2),
                    (405.0, -45.0), (402.0, -50.8), (351.0, -50.8), (346.6, -46.0)],
                   [0, 0, 2.0, 2.0, 0, 0, 3.0, 5.0, 5.0, 3.0], 5)
    guard = prism_xz("Trigger_guard", outer, -4.6, 4.6, C, "Steel_black")
    inner = fillet([(358.5, -10.0), (401.8, -10.0), (401.8, -48.2), (358.5, -48.2)], [0, 0, 6.0, 7.0], 6)
    # прилив переводчика остаётся в коробке — внутренний вырез скобы перед ним
    boolean(guard, prism_xz("_gin", inner, -8, 8, C))
    boolean(guard, cyl("_gsel", -30, 30, 3.1, C, axis="Y", cy=352.0, cz=-29.5, seg=24))
    finish(guard, 1.1, 3, 35)
    out["guard"] = guard

    # заклёпки и штифты коробки (головки с обеих сторон)
    pins = [(300.0, -18.0, 2.1), (330.0, -18.0, 2.1), (372.0, -9.0, 2.4), (440.0, -6.0, 2.0),
            (465.0, -8.0, 2.0), (409.0, -38.0, 2.2)]
    for i, (x, z, r) in enumerate(pins):
        for s in (-1, 1):
            if s == -1 and abs(x - 372.0) < 0.1:
                pass
            p = lathe(f"Receiver_pin_{i}_{'R' if s < 0 else 'L'}", [(0, 0), (0, r), (0.35, r * 0.92), (0.6, r * 0.6), (0.7, 0)],
                      C, "Steel_black", 24, 0, 0)
            p.rotation_euler = (0, 0, -math.pi / 2 if s < 0 else math.pi / 2)
            p.location = (x * 0.001, s * (LOWER_W - 0.05) * 0.001, z * 0.001)
            from lib import apply_transform
            apply_transform(p)
            auto_sharp(p, 40)
    return out
