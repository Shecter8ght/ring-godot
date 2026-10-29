# AR-15: нижний ресивер «из заготовки» (раструб шахты, встроенная скоба — как у листинга Fab) и ударно-спусковой
# механизм: курок, спуск, разобщитель, автоспуск, переводчик с двумя флажками, защёлка магазина, затворная задержка,
# оси сборки и разборки, фиксатор буфера.
import math
import bpy
from lib import (MM, SPLIT_Z, REAR_TOP_Z, STEP_X, STEP_R, LOWER_HALF_W, GRIP_TOP_Z, LOWER_REAR, UPPER_REAR, PIVOT_PIN, TAKEDOWN_PIN, AUTOSEAR_PIN, SELECTOR,
                 TRIGGER_PIN, HAMMER_PIN, MAG_BUTTON, GUARD_X, GUARD_Z, MAGWELL_FRONT, BUFFER_R, fillet, arc_pts,
                 prism_xz, prism_yz, prism_xy, box, cyl, lathe, boolean, finish, join, bevel_edges, auto_sharp, material)
from part_upper import LUG_HALF_W, PIN_R

FCG_HALF_W = 12.2            # боковины кармана УСМ (снаружи)
FCG_POCKET_HALF = 9.4        # карман УСМ внутри
WELL_IN_HALF_W = 11.7        # шахта внутри 23.4 мм (замер 15 ресиверов: 0.905″ + зазор магазину)
WELL_REAR_OUT = -58.0        # задняя стенка шахты снаружи
WELL_REAR_IN = -54.7         # шахта внутри 62.5 мм; задняя стенка ≈3.3 мм
WELL_FRONT_IN = 7.8          # передняя стенка 3 мм
WELL_BOTTOM_FRONT = -56.0
WELL_BOTTOM_REAR = -70.0
BOTTOM_Z = GUARD_Z[1]        # низ корпуса над спуском (−50.1)
TOWER_R = 17.3                # башня буферной трубки: гайка R 16.3; за кнопкой досылателя вдоль её оси свободно
TOWER_X = (LOWER_REAR, UPPER_REAR)
PART_W = 9.3                 # толщина курка и спуска (0.37″)
BOLT_CATCH_PIVOT = (-50.5, 15.4, -19.0)   # ось затворной задержки — вдоль X (над защёлкой магазина)
GRIP_ANGLE = 18.0            # наклон рукояти от вертикали, град
RETAINER_X = UPPER_REAR + 2.0   # фиксатор буфера — перед торцом трубки, её кромка держит головку


GUARD_POST_X = GUARD_X[0] - 5.0      # задняя грань стойки скобы — вертикальная, к ней примыкает выступ рукояти
GUARD_PIN = (-115.6, -73.6, 1.5)     # штифт скобы в заднем нижнем углу (x, z, r)
PIVOT_EAR_R = 6.3                    # скругление «уха» оси сборки вокруг оси (перёд x 24.1 — в выемке цевья)
PIVOT_BOSS_R = 5.4                   # втулка оси сборки снаружи уха (вокруг головки оси — кольцо 1 мм)
PIVOT_BOSS_H = 0.7


def guard_and_well_profile():
    """Боковой профиль нижнего ресивера: шахта, низ корпуса, скоба, площадка рукояти, задняя часть до башни."""
    pts = [
        (MAGWELL_FRONT, SPLIT_Z),                  # верх передней стенки шахты
        (MAGWELL_FRONT, -40.0),
        (MAGWELL_FRONT + 4.3, WELL_BOTTOM_FRONT + 3.0),   # раструб вперёд (до 15.1)
        (MAGWELL_FRONT + 3.6, WELL_BOTTOM_FRONT),
        (WELL_REAR_OUT + 1.0, WELL_BOTTOM_REAR),          # скошенная губа шахты
        (WELL_REAR_OUT - 2.9, GUARD_Z[0] - 6.5),          # переднее ухо скобы
        (GUARD_POST_X, GUARD_Z[0] - 6.5),                 # низ перекладины сзади
        (GUARD_POST_X, GRIP_TOP_Z),                       # задняя стойка — вертикаль, шов с выступом рукояти
        (-186.0, GRIP_TOP_Z),                             # площадка рукояти; угол острый — спинка рукояти кончается заподлицо
        (LOWER_REAR + 0.5, -22.0),                        # задняя грань под башней (выше — башня буферной трубки)
        (LOWER_REAR + 0.5, SPLIT_Z),
    ]
    return fillet(pts, [1.5, 0, 6.0, 2.5, 3.0, 6.0, 2.5, 0, 0.8, 3.0, 0], seg=5)


def build(ctx):
    C = ctx["coll"]["Lower"]
    F = ctx["coll"]["Fire_control"]
    out = {}
    side = guard_and_well_profile()
    body = prism_xz("Lower_receiver", side, -FCG_HALF_W, FCG_HALF_W, C, "Alu_anodized")
    # шахта магазина шире корпуса УСМ
    well = prism_xz("lower_well", fillet([
        (MAGWELL_FRONT, SPLIT_Z), (MAGWELL_FRONT, -40.0), (MAGWELL_FRONT + 4.3, WELL_BOTTOM_FRONT + 3.0),
        (MAGWELL_FRONT + 3.6, WELL_BOTTOM_FRONT), (WELL_REAR_OUT + 1.0, WELL_BOTTOM_REAR), (WELL_REAR_OUT - 1.0, WELL_BOTTOM_REAR + 6.0),
        (WELL_REAR_OUT - 1.0, SPLIT_Z)], [1.5, 0, 6.0, 2.5, 3.0, 2.0, 0], 5), -LOWER_HALF_W, LOWER_HALF_W, C, "Alu_anodized")
    boolean(body, well, "UNION")
    # раструб снизу шахты — расширение по бокам
    flare = prism_xz("lower_flare", fillet([
        (MAGWELL_FRONT + 4.4, WELL_BOTTOM_FRONT + 6.0), (MAGWELL_FRONT + 3.6, WELL_BOTTOM_FRONT),
        (WELL_REAR_OUT + 1.0, WELL_BOTTOM_REAR), (WELL_REAR_OUT + 1.0, WELL_BOTTOM_REAR + 6.0)], [1.5, 2, 2, 1.5], 3),
        -LOWER_HALF_W - 1.2, LOWER_HALF_W + 1.2, C, "Alu_anodized")
    boolean(body, flare, "UNION")
    # «уши» оси сборки (спереди) и оси разборки (сзади) — по бокам проушин верхнего ресивера
    for nm, (px, pz), half in (("pivot", PIVOT_PIN, LOWER_HALF_W), ("takedown", TAKEDOWN_PIN, FCG_HALF_W)):
        if nm == "pivot":
            r = PIVOT_EAR_R
            arc = arc_pts(px, pz, r, -90.0, 90.0, 24)
            prof = [(8.6, -30.0), (MAGWELL_FRONT, -30.0), (MAGWELL_FRONT, pz - r)] + arc + [(8.6, pz + r)]
            radii = [0, 0, 4.5] + [0] * len(arc) + [1.2]
            ear = prism_xz(f"lower_ear_{nm}", fillet(prof, radii, 6), -half, half, C, "Alu_anodized")
            boolean(body, ear, "UNION")
            # втулка оси снаружи каждого уха
            for s_ in (-1, 1):
                y0, y1 = (half - 0.5, half + PIVOT_BOSS_H) if s_ > 0 else (-half - PIVOT_BOSS_H, -half + 0.5)
                boolean(body, cyl("lower_pivot_boss", y0, y1, PIVOT_BOSS_R, C, "Alu_anodized", seg=48, cy=px, cz=pz, axis="Y",
                                  ch=0.35), "UNION")
        else:
            # сзади боковины целиком подняты до REAR_TOP_Z — ось разборки проходит через них
            rw = prism_xz("lower_rear_walls", fillet([(LOWER_REAR + 1.5, SPLIT_Z - 1.0), (STEP_X, SPLIT_Z - 1.0), (STEP_X, REAR_TOP_Z),
                                                      (LOWER_REAR + 1.5, REAR_TOP_Z)], [0, 0, STEP_R, 0], 8),
                          -FCG_HALF_W, FCG_HALF_W, C, "Alu_anodized")
            boolean(body, rw, "UNION")
        if nm == "pivot":
            # паз под проушину верхнего: дно вогнутое спереди (носик шахты между ушами — плавная выемка)
            boolean(body, prism_xz("cut_slot_pivot", fillet([(7.0, pz - 9.0), (px + 10.0, pz - 9.0), (px + 10.0, pz + 10.0),
                                                              (7.0, pz + 10.0)], [0, 6.0, 0, 0], 8),
                                   -LUG_HALF_W, LUG_HALF_W, C))
        else:
            boolean(body, box(f"cut_slot_{nm}", px - 10.0, px + 10.0, -LUG_HALF_W, LUG_HALF_W, pz - 8.0, pz + 10.0, C))
        boolean(body, cyl(f"cut_{nm}_pin", -25, 25, PIN_R + 0.05, C, seg=32, cy=px, cz=pz, axis="Y"))
    # башня буферной трубки
    tower = lathe("lower_tower", [(TOWER_X[0], 0.0), (TOWER_X[0], TOWER_R - 1.5), (TOWER_X[0] + 1.5, TOWER_R),
                                  (TOWER_X[1], TOWER_R), (TOWER_X[1], 0.0)], C, "Alu_anodized", seg=64)
    boolean(body, tower, "UNION")
    boolean(body, cyl("cut_tower", TOWER_X[0] - 5, TOWER_X[1], BUFFER_R + 0.15, C, seg=64))
    # карман УСМ сверху и шахта магазина насквозь
    boolean(body, box("cut_fcg", -146.0, -69.0, -FCG_POCKET_HALF, FCG_POCKET_HALF, BOTTOM_Z + 4.2, 5.0, C))
    boolean(body, box("cut_fcg_rear", -170.0, -146.0, -FCG_POCKET_HALF, FCG_POCKET_HALF, -24.0, 5.0, C))
    # посередине сзади — под раму и буфер (боковины выше, середина ниже оси)
    boolean(body, box("cut_rear_center", UPPER_REAR - 1.5, -145.0, -FCG_POCKET_HALF, FCG_POCKET_HALF, -13.4, 5.0, C))
    boolean(body, box("cut_fcg_top", -146.0, -69.0, -FCG_POCKET_HALF, FCG_POCKET_HALF, -30.0, 5.0, C))
    well_cut = prism_xz("cut_well", [(WELL_FRONT_IN, 5.0), (WELL_FRONT_IN, -90.0), (WELL_REAR_IN, -90.0), (WELL_REAR_IN, 5.0)],
                        -WELL_IN_HALF_W, WELL_IN_HALF_W, C)
    boolean(body, well_cut)
    # прорезь в дне кармана — перо спуска выходит в скобу
    boolean(body, box("cut_trig_slot", TRIGGER_PIN[0] - 13.0, TRIGGER_PIN[0] + 14.5, -5.2, 5.2, BOTTOM_Z - 6.0, BOTTOM_Z + 5.0, C))
    # раструб изнутри — фаска входа
    flare_in = prism_yz("cut_well_flare", [(-WELL_IN_HALF_W - 3.0, -100.0), (WELL_IN_HALF_W + 3.0, -100.0),
                                           (WELL_IN_HALF_W + 3.0, WELL_BOTTOM_REAR - 0.5), (WELL_IN_HALF_W, WELL_BOTTOM_REAR + 7.0),
                                           (-WELL_IN_HALF_W, WELL_BOTTOM_REAR + 7.0), (-WELL_IN_HALF_W - 3.0, WELL_BOTTOM_REAR - 0.5)],
                        WELL_REAR_IN - 4.0, WELL_FRONT_IN + 4.0, C)
    boolean(body, flare_in)
    # проём скобы
    gx0, gx1 = GUARD_X
    gz0, gz1 = GUARD_Z
    opening = prism_xz("cut_guard", fillet([(gx0, gz1), (gx1, gz1), (gx1, gz0), (gx0, gz0)], [3.0, 3.0, 10.0, 11.0], 8),
                       -30, 30, C)
    boolean(body, opening)
    # скоба уже корпуса: снимаем бока под проёмом
    for s in (-1, 1):
        y0, y1 = (6.6, 30.0) if s > 0 else (-30.0, -6.6)
        boolean(body, box(f"cut_guard_side{s}", GUARD_POST_X - 3.0, gx1 + 1.0, y0, y1, gz0 - 8.0, gz1 - 1.6, C))
    # отверстия осей: переводчик, спуск, курок, автоспуск, защёлка магазина
    for nm, (px, pz), r in (("selector", SELECTOR, 4.75), ("trigger", TRIGGER_PIN, 1.96), ("hammer", HAMMER_PIN, 1.96),
                            ("autosear", AUTOSEAR_PIN, 1.96)):
        boolean(body, cyl(f"cut_{nm}", -30, 30, r, C, seg=24, cy=px, cz=pz, axis="Y"))
    # защёлка магазина: поперечный канал, кнопка справа в ограждении, рычаг слева в выемке
    mx, mz = MAG_BUTTON
    boolean(body, box("cut_catch_ch", mx - 4.1, mx + 4.1, -30, 30, mz - 3.5, mz + 3.5, C))
    fence = prism_xz("lower_catch_fence", fillet([(mx - 9.0, mz - 9.5), (mx + 9.0, mz - 9.5), (mx + 9.0, SPLIT_Z - 0.6), (mx - 9.0, SPLIT_Z - 0.6)], [7.5, 7.5, 3.0, 3.0], 8),
                     -LOWER_HALF_W - 1.4, -FCG_HALF_W + 0.4, C, "Alu_anodized")
    boolean(body, fence, "UNION")
    boolean(body, cyl("cut_button", -40, -FCG_HALF_W + 1.0, 5.4, C, seg=32, cy=mx, cz=mz, axis="Y"))
    boolean(body, box("cut_catch_left", mx - 5.0, mx + 26.0, LOWER_HALF_W - 1.4, 30, mz - 4.2, mz + 4.2, C))
    # окно в левой стенке шахты под зуб защёлки
    boolean(body, box("cut_catch_window", mx + 16.5, mx + 23.5, WELL_IN_HALF_W - 1.0, LOWER_HALF_W, mz - 2.6, mz + 2.6, C))
    # затворная задержка: выемка на левом боку над защёлкой магазина и «уши» с осью вдоль X
    bx, by, bz = BOLT_CATCH_PIVOT
    boolean(body, box("cut_bc_recess", bx - 8.0, bx + 8.0, LOWER_HALF_W - 1.6, 30, bz - 5.0, SPLIT_Z + 0.5, C))
    boolean(body, box("cut_bc_recess_low", bx - 8.0, bx + 8.0, LOWER_HALF_W - 2.6, 30, bz - 5.0, bz + 0.5, C))
    for x0, x1 in ((bx - 12.0, bx - 8.0), (bx + 8.0, bx + 12.0)):
        ear = prism_yz("lower_bc_ear", fillet([(LOWER_HALF_W - 1.5, bz - 3.5), (by + 2.4, bz - 3.5), (by + 2.4, SPLIT_Z),
                                               (LOWER_HALF_W - 1.5, SPLIT_Z)], [0, 1.5, 0, 0], 3), x0, x1, C, "Alu_anodized")
        boolean(body, ear, "UNION")
    boolean(body, cyl("cut_bc_pin", bx - 14, bx + 14, 1.2, C, seg=16, cy=by, cz=bz, axis="X"))
    # канал зуба задержки из выемки внутрь, над шахтой
    boolean(body, box("cut_bc_slot", bx - 6.0, bx + 6.0, 6.5, LOWER_HALF_W, bz - 1.5, 5.0, C))
    # фиксатор буфера: вертикальное отверстие перед башней
    boolean(body, cyl("cut_retainer", -40, -10, 1.95, C, seg=16, cy=RETAINER_X, cz=0.0, axis="Z"))
    # рифление спереди на шахте (обе стороны) и неглубокие панели на боках шахты
    for sgn in (-1, 1):
        for k in range(8):
            zz = -24.0 - k * 3.3
            y0, y1 = (LOWER_HALF_W - 0.7, LOWER_HALF_W + 4) if sgn > 0 else (-LOWER_HALF_W - 4, -LOWER_HALF_W + 0.7)
            boolean(body, prism_xz(f"cut_rib{sgn}{k}", fillet([(-3.0, zz - 0.75), (MAGWELL_FRONT - 2.0, zz - 0.75), (MAGWELL_FRONT - 2.0, zz + 0.75),
                                                                (-3.0, zz + 0.75)], 0.7, 3), y0, y1, C))
        y0, y1 = (LOWER_HALF_W - 0.8, LOWER_HALF_W + 4) if sgn > 0 else (-LOWER_HALF_W - 4, -LOWER_HALF_W + 0.8)
        boolean(body, prism_xz(f"cut_panel{sgn}", fillet([(-38.0, -52.0), (-6.5, -49.0), (-6.5, -23.0), (-38.0, -23.0)], 3.0, 5), y0, y1, C))
    # квадратные выемки сеткой слева (образец Fab): на панели шахты 2 × 3 у задней кромки, над передом скобы 2 × 2
    for nm, xs, zs, y_face in (("well", (-33.6, -30.0), (-46.0, -42.4, -38.8), LOWER_HALF_W - 0.8),
                               ("fcg", (-66.4, -62.8), (-45.6, -42.0), FCG_HALF_W)):
        for i, xx in enumerate(xs):
            for j, zz in enumerate(zs):
                sq = prism_xz(f"cut_sq_{nm}{i}{j}", fillet([(xx - 1.2, zz - 1.2), (xx + 1.2, zz - 1.2), (xx + 1.2, zz + 1.2),
                                                             (xx - 1.2, zz + 1.2)], 0.4, 2), y_face - 0.8, y_face + 4.0, C)
                boolean(body, sq)
    # отверстие винта рукояти снизу (под углом рукояти)
    gs = cyl("cut_grip_screw", -14.0, 6.0, 2.6, C, seg=20, axis="Z", cy=0.0, cz=0.0)
    gs.rotation_euler = (0, math.radians(18.0), 0)
    gs.location = (-158.0 * MM, 0, (GRIP_TOP_Z + 2.0) * MM)
    from lib import apply_transform as _at
    _at(gs)
    boolean(body, gs)
    # низ скобы скруглён
    bevel_edges(body, lambda n1, n2: n1.z < -0.9 and abs(n2.y) > 0.9, w=2.0, seg=4,
                where=lambda p: GUARD_POST_X - 4.0 < p.x < GUARD_X[1] - 2.0 and p.z < GUARD_Z[0] - 2.0)
    # кромки проёма скобы — заметная фаска с обеих сторон (как на скрине владельца)
    bevel_edges(body, lambda n1, n2: abs(n1.y) > 0.9 and abs(n2.y) < 0.2, w=0.9, seg=3, clamp=True,
                where=lambda p: gx0 - 1.0 < p.x < gx1 + 0.5 and gz0 - 1.0 < p.z < gz1 - 1.0 and 6.0 < abs(p.y) < 7.2)
    # продольный паз на перекладине скобы с обеих сторон
    for s_ in (-1, 1):
        y0, y1 = (6.6 - 0.9, 9.0) if s_ > 0 else (-9.0, -6.6 + 0.9)
        slot = prism_xz(f"cut_guard_slot{s_}", fillet([(-99.0, -75.0), (-72.5, -75.0), (-72.5, -72.6), (-99.0, -72.6)], 1.15, 4), y0, y1, C)
        boolean(body, slot)
    gpx, gpz, gpr = GUARD_PIN
    boolean(body, cyl("cut_guard_pin", -20, 20, gpr + 0.05, C, seg=24, cy=gpx, cz=gpz, axis="Y"))
    finish(body, w=0.5, seg=2, angle=35)
    out["body"] = body
    # штифт скобы — разрезной, торцы чуть утоплены
    pin = cyl("Guard_pin", -6.3, 6.3, gpr - 0.05, C, "Steel_black", seg=24, cy=gpx, cz=gpz, axis="Y", ch=0.25)
    boolean(pin, cyl("cut_guard_pin_bore", -7, 7, gpr - 0.6, C, seg=20, cy=gpx, cz=gpz, axis="Y"))
    boolean(pin, box("cut_guard_pin_slit", gpx - 0.2, gpx + 0.2, -7, 7, gpz - gpr - 1.0, gpz - gpr + 1.0, C))
    out["guard_pin"] = pin

    # --- оси сборки и разборки: головка справа (−Y), выталкиваются вправо ---
    for nm, (px, pz) in (("Pivot_pin", PIVOT_PIN), ("Takedown_pin", TAKEDOWN_PIN)):
        half = LOWER_HALF_W + PIVOT_BOSS_H if nm == "Pivot_pin" else FCG_HALF_W
        pr = PIN_R - 0.06
        hin = -0.05 if nm == "Pivot_pin" else 0.2           # головка оси сборки лежит на втулке, не заходит в неё
        prof = [(-half - 1.2, 0.0), (-half - 1.2, 4.1), (-half + hin, 4.4), (-half + hin, pr), (half - 0.3, pr),
                (half, pr - 0.4), (half, 0.0)]
        p = lathe(nm, prof, C, "Steel_black", seg=32, cy=0.0, cz=0.0)
        p.rotation_euler = (0, 0, math.pi / 2)  # ось вдоль Y
        from lib import apply_transform
        apply_transform(p)
        p.location = (px * MM, 0, pz * MM)
        apply_transform(p)
        # канавка фиксатора на стержне
        boolean(p, box(nm + "_groove", px - PIN_R - 1, px - PIN_R + 0.6, -half + 3.0, half - 4.0, pz - 1.0, pz + 1.0, C))
        auto_sharp(p, 35)
        out[nm] = p

    # --- фиксатор буфера ---
    out["buffer_retainer"] = lathe("Buffer_retainer", [(-24.0, 0.0), (-24.0, 1.9), (-17.6, 1.9), (-17.6, 2.6), (-15.0, 2.6),
                                                       (-15.0, 1.6), (-11.8, 1.6), (-11.4, 1.2), (-11.4, 0.0)], C, "Steel_black", seg=20)
    rt = out["buffer_retainer"]
    rt.rotation_euler = (0, -math.pi / 2, 0)
    rt.location = (RETAINER_X * MM, 0, 0)
    from lib import apply_transform
    apply_transform(rt)
    auto_sharp(rt, 35)

    out.update(fire_control(F))
    out.update(selector(F))
    out.update(mag_catch(F))
    out["bolt_catch"] = bolt_catch(F)
    return out


def fire_control(F):
    o = {}
    tx, tz = TRIGGER_PIN
    hx, hz = HAMMER_PIN
    half = PART_W / 2
    # спусковой крючок (фото PEO, увеличенный кадр): перо — серп, открытый вперёд; передняя грань вогнута под палец,
    # вверху перо широкое и уходит вперёд к корпусу спуска, кончик почти под осью — в ~1 мм над перекладиной скобы.
    # Корпус: нос вперёд под зуб курка, хвост назад под кулачок переводчика.
    cl = [(tx + 7.5, tz - 8.0), (tx + 6.6, tz - 14.0), (tx + 4.4, tz - 19.0), (tx + 1.2, tz - 23.5), (tx - 0.6, tz - 27.9),
          (tx - 0.9, tz - 31.8), (tx - 0.2, tz - 35.2), (tx + 0.9, tz - 37.6)]
    wd = [10.0, 8.2, 6.6, 5.6, 5.0, 4.5, 4.0, 3.6]
    front, back = [], []
    for i, (cx, cz) in enumerate(cl):
        p0 = cl[max(0, i - 1)]; p1 = cl[min(len(cl) - 1, i + 1)]
        dx, dz = p1[0] - p0[0], p1[1] - p0[1]
        ln = math.hypot(dx, dz)
        nx, nz = -dz / ln, dx / ln                     # нормаль вперёд (+X)
        if nx < 0:
            nx, nz = -nx, -nz
        front.append((cx + nx * wd[i] / 2, cz + nz * wd[i] / 2))
        back.append((cx - nx * wd[i] / 2, cz - nz * wd[i] / 2))
    a_tip = math.degrees(math.atan2(nz, nx))
    tip = arc_pts(cl[-1][0], cl[-1][1], wd[-1] / 2, a_tip, a_tip - 180.0, 7)
    body = [(tx + 22.0, tz + 1.5), (tx + 22.0, tz - 2.6), (tx + 10.0, tz - 6.0)] + front[1:] + tip[1:-1] + list(reversed(back))[:-1] + \
           [(tx - 6.0, tz - 8.0), (tx - 26.0, tz - 6.0), (tx - 31.0, tz - 4.6), (tx - 31.0, tz - 0.4), (tx - 22.0, tz + 0.2), (tx - 8.0, tz + 4.5)]
    rad = [1.0, 1.0, 3.0] + [0] * (len(front) - 1) + [0] * (len(tip) - 2) + [0] * (len(back) - 1) + [3.0, 1.0, 1.5, 1.0, 2.0, 2.0]
    t = prism_xz("Trigger", fillet(body, rad, seg=3), -half, half, F, "Steel_black")
    # перо уже корпуса спуска: ширина 7.8 мм ниже корпуса, лицевая грань скруглена
    for sgn in (-1, 1):
        y0, y1 = (3.9, 10) if sgn > 0 else (-10, -3.9)
        boolean(t, box(f"cut_trig_thin{sgn}", tx - 20.3, tx + 20.3, y0, y1, tz - 60, tz - 13.3, F))
    boolean(t, cyl("cut_trig_pin", -20, 20, 1.95, F, seg=20, cy=tx, cz=tz, axis="Y"))
    finish(t, w=0.9, seg=3, angle=35)
    o["trigger"] = t
    # разобщитель — пластина над хвостом спуска
    dis = prism_xz("Disconnector", fillet([(tx + 6.0, tz + 2.6), (tx - 24.0, tz + 2.2), (tx - 26.0, tz + 4.4), (tx - 21.0, tz + 6.2),
                                            (tx - 6.0, tz + 4.7), (tx + 6.0, tz + 4.7)], [1.2, 1.0, 1.0, 1.2, 1.0, 1.2], 3),
                   -2.3, 2.3, F, "Steel_black")
    boolean(dis, cyl("cut_dis_pin", -20, 20, 1.95, F, seg=20, cy=tx, cz=tz + 0.0, axis="Y"))
    finish(dis, w=0.2, seg=2, angle=35)
    o["disconnector"] = dis
    # курок в положении «спущен»: головка отклонена назад, её передняя грань — ударный торец — стоит на головке
    # ударника (x = FP_HEAD, ось канала); взвод — поворот назад ещё на HAMMER_COCK_DEG вокруг оси.
    fx = -84.4 - hx                       # ударный торец относительно оси курка (головка ударника в −84)
    hub = arc_pts(hx, hz, 7.0, -60, -160, 16)          # ступица снизу: от переднего низа к заднему
    ham = hub + [(hx - 7.4, hz + 1.5), (hx - 10.2, hz + 3.6), (hx - 10.6, hz + 6.4), (hx - 8.0, hz + 7.2),   # крюк разобщителя
                 (hx - 9.5, hz + 12.0), (hx + fx - 11.0, hz + 18.5), (hx + fx - 11.5, hz + 24.0),         # шейка и затылок головки
                 (hx + fx - 7.0, hz + 26.6), (hx + fx, hz + 26.0), (hx + fx + 0.4, hz + 21.0),            # ударный торец
                 (hx + fx - 1.5, hz + 17.5), (hx + 1.5, hz + 9.0), (hx + 6.0, hz + 5.0), (hx + 7.6, hz + 1.0)]   # передняя грань и зуб
    rad = [0] * len(hub) + [1.0, 1.0, 1.0, 1.0, 3.0, 3.0, 2.0, 2.0, 0.6, 0.8, 2.0, 4.0, 1.5, 1.0]
    h = prism_xz("Hammer", fillet(ham, rad, seg=3), -half, half, F, "Steel_black")
    boolean(h, cyl("cut_ham_pin", -20, 20, 1.95, F, seg=20, cy=hx, cz=hz, axis="Y"))
    # головка уже ступицы (как у серийных курков)
    for sgn in (-1, 1):
        y0, y1 = (3.6, 10) if sgn > 0 else (-10, -3.6)
        boolean(h, box(f"cut_ham_thin{sgn}", hx - 30.3, hx + 10.3, y0, y1, hz + 13.4, hz + 35, F))
    finish(h, w=0.3, seg=2, angle=35)
    o["hammer"] = h
    # автоспуск (рычажок над переводчиком)
    ax, az = AUTOSEAR_PIN
    s = prism_xz("Auto_sear", fillet([(ax - 4.0, az - 3.0), (ax + 14.0, az - 1.0), (ax + 15.0, az + 2.0), (ax - 4.0, az + 3.5)], 1.2, 3),
                 -4.0, 4.0, F, "Steel_black")
    boolean(s, cyl("cut_as_pin", -20, 20, 1.95, F, seg=20, cy=ax, cz=az, axis="Y"))
    finish(s, w=0.2, seg=2, angle=35)
    o["auto_sear"] = s
    # пружины: курка — витки на оси курка по обе стороны, усики назад на ось спуска; спуска — витки на оси спуска,
    # усики вперёд на дно кармана (видны при раскрытом ресивере)
    o.update(fcg_springs(F))
    # оси: спуск, курок, автоспуск
    for nm, (px, pz) in (("Trigger_pin", TRIGGER_PIN), ("Hammer_pin", HAMMER_PIN), ("Auto_sear_pin", AUTOSEAR_PIN)):
        o[nm] = cyl(nm, -FCG_HALF_W + 0.4, FCG_HALF_W - 0.4, 1.95, F, "Steel_black", seg=20, cy=px, cz=pz, axis="Y", ch=0.3)
    return o


def _wire(name, pts, r, F, seg=12):
    """Проволока по ломаной (мм) — трубка с круглым сечением. Сечение переносится вдоль линии без поворота
    (параллельный перенос), иначе на изгибах пружин и петель сечение перекручивается и сминается."""
    import bmesh
    from mathutils import Vector
    from lib import v as vmm
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = []
    P = [Vector(q) for q in pts]
    T = [(P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).normalized() for i in range(len(P))]
    a = Vector((0, 0, 1)) if abs(T[0].z) < 0.9 else Vector((1, 0, 0))
    n1 = T[0].cross(a).normalized()
    for i, c in enumerate(P):
        if i > 0:
            n1 = T[i - 1].rotation_difference(T[i]) @ n1
            n1 = (n1 - T[i] * n1.dot(T[i])).normalized()
        n2 = T[i].cross(n1).normalized()
        rings.append([bm.verts.new(vmm(*(c + (n1 * math.cos(2 * math.pi * k / seg) + n2 * math.sin(2 * math.pi * k / seg)) * r)))
                      for k in range(seg)])
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(seg):
            j = (k + 1) % seg
            bm.faces.new((r0[k], r0[j], r1[j], r1[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for pl in me.polygons:
        pl.use_smooth = True
    o = bpy.data.objects.new(name, me)
    F.objects.link(o)
    o.data.materials.append(material("Spring_steel"))
    o["_fin"] = 1
    return o


def _coil_pts(cx, cz, r, y0, y1, turns, a0=0.0):
    pts = []
    n = int(turns * 20)
    for k in range(n + 1):
        t = k / n
        a = math.radians(a0) + 2 * math.pi * turns * t
        pts.append((cx + r * math.cos(a), y0 + (y1 - y0) * t, cz + r * math.sin(a)))
    return pts


def fcg_springs(F):
    o = {}
    hx, hz = HAMMER_PIN
    tx, tz = TRIGGER_PIN
    w = 0.55                                     # проволока Ø1.1
    rc = 1.96 + 0.15 + w                          # виток вокруг оси
    for s in (-1, 1):
        y0, y1 = s * (PART_W / 2 + 0.8), s * (PART_W / 2 + 0.8 + 2.6)
        # курок: виток, затем усик назад-вниз и полка на оси спуска сверху
        coil = _coil_pts(hx, hz, rc, y0, y1, 2.25, a0=200.0)
        end = coil[-1]
        leg = [end, (hx - 9.0, end[1], hz - 4.5), (tx + 2.0, end[1], tz + 1.96 + w), (tx - 3.0, end[1], tz + 1.96 + w)]
        o[f"Hammer_spring{s}"] = _wire(f"Hammer_spring_{'L' if s > 0 else 'R'}", coil + leg[1:], w, F)
        # спуск: виток вокруг оси спуска, усик вперёд на дно кармана
        y0, y1 = s * (PART_W / 2 + 0.8), s * (PART_W / 2 + 0.8 + 2.2)
        coil = _coil_pts(tx, tz, rc, y0, y1, 2.0, a0=-20.0)
        end = coil[-1]
        floor = BOTTOM_Z + 4.2 + w + 0.1
        leg = [end, (tx + 8.0, end[1], tz - 6.0), (tx + 15.0, end[1], floor), (tx + 19.0, end[1], floor)]
        o[f"Trigger_spring{s}"] = _wire(f"Trigger_spring_{'L' if s > 0 else 'R'}", coil + leg[1:], w, F)
    return o


def selector(F):
    """Переводчик: вал поперёк, длинный флажок слева, короткий справа. 0° — «предохранитель» (флажок вперёд)."""
    sx, sz = SELECTOR
    o = {}
    shaft = lathe("Selector", [(-FCG_HALF_W - 0.6, 0.0), (-FCG_HALF_W - 0.6, 4.7), (FCG_HALF_W + 0.6, 4.7), (FCG_HALF_W + 0.6, 0.0)],
                  F, "Steel_black", seg=32, cy=0.0, cz=0.0)
    shaft.rotation_euler = (0, 0, math.pi / 2)
    from lib import apply_transform
    apply_transform(shaft)
    shaft.location = (sx * MM, 0, sz * MM)
    apply_transform(shaft)
    # вырез-«кулачок» на валу (над хвостом спуска)
    boolean(shaft, box("cut_sel_cam", sx - 6, sx + 6, -4.8, 4.8, sz + 0.5, sz + 6, F))
    boolean(shaft, box("cut_sel_cam_r", sx - 6, sx - 0.5, -4.8, 4.8, sz - 6, sz + 6, F))
    # флажки: круглая ступица с фаской, флажок сужается к площадке под палец (выше флажка, с поперечным рифлением)
    for s_, length, nm in ((1, 14.5, "Selector_lever_L"), (-1, 9.5, "Selector_lever_R")):
        yb, yh = FCG_HALF_W + 0.5, FCG_HALF_W + 2.7
        yt = FCG_HALF_W + (4.2 if s_ > 0 else 3.6)

        def ys(a_, b_):
            return min(a_ * s_, b_ * s_), max(a_ * s_, b_ * s_)
        outline = [(sx + length - 4.0, sz - 2.6), (sx + length - 4.0, sz + 2.6)] + arc_pts(sx, sz, 6.6, 33, 327, 28)
        y0, y1 = ys(yb, yh)
        lev = prism_xz(nm, fillet(outline, [1.0, 1.0] + [0] * (len(outline) - 2), 3), y0, y1, F, "Steel_black")
        ta, tb = ys(yb + 0.3, yt)
        tab = prism_xz(nm + "_tab", fillet([(sx + length - 7.5, sz - 4.3), (sx + length + 1.6, sz - 3.5), (sx + length + 1.6, sz + 3.5),
                                            (sx + length - 7.5, sz + 4.3)], [1.5, 2.8, 2.8, 1.5], 4), ta, tb, F, "Steel_black")
        boolean(lev, tab, "UNION")
        for k in range(4):
            xx = sx + length - 5.6 + k * 1.95
            ya, yb2 = ys(yt - 0.45, yt + 2.0)
            boolean(lev, box(f"{nm}_ser{k}", xx - 0.45, xx + 0.45, ya, yb2, sz - 6, sz + 6, F))
        # риска-указатель на ступице (по флажку)
        ya, yb2 = ys(yh - 0.4, yh + 2.0)
        boolean(lev, box(f"{nm}_mark", sx - 5.6, sx - 2.4, ya, yb2, sz - 0.4, sz + 0.4, F))
        finish(lev, w=0.45, seg=2, angle=35)
        o[nm] = lev
    o["selector"] = shaft
    return o


def mag_catch(F):
    mx, mz = MAG_BUTTON
    o = {}
    # кнопка справа: цилиндр с рифлёным торцом
    btn = lathe("Mag_button", [(-LOWER_HALF_W - 1.0, 0.0), (-LOWER_HALF_W - 1.0, 4.7), (-LOWER_HALF_W - 0.6, 5.1),
                               (-LOWER_HALF_W + 4.0, 5.1), (-LOWER_HALF_W + 4.0, 0.0)], F, "Steel_black", seg=32, cy=0.0, cz=0.0)
    btn.rotation_euler = (0, 0, math.pi / 2)
    from lib import apply_transform
    apply_transform(btn)
    btn.location = (mx * MM, 0, mz * MM)
    apply_transform(btn)
    for k in range(3):
        r0 = 1.2 + k * 1.3
        ring = lathe("btn_ring", [(-LOWER_HALF_W - 1.4, r0), (-LOWER_HALF_W - 1.4, r0 + 0.45), (-LOWER_HALF_W - 0.7, r0 + 0.45),
                                  (-LOWER_HALF_W - 0.7, r0)], F, None, seg=32, cy=0.0, cz=0.0)
        ring.rotation_euler = (0, 0, math.pi / 2)
        apply_transform(ring)
        ring.location = (mx * MM, 0, mz * MM)
        apply_transform(ring)
        boolean(btn, ring)
    auto_sharp(btn, 35)
    o["mag_button"] = btn
    # защёлка: поперечная тяга и рычаг с зубом на левом боку
    bar = box("Mag_catch", mx - 3.2, mx + 3.2, -LOWER_HALF_W + 3.0, LOWER_HALF_W - 1.0, mz - 2.6, mz + 2.6, F, "Steel_black")
    arm = prism_xz("mag_catch_arm", fillet([(mx - 4.0, mz - 3.6), (mx + 25.0, mz - 3.6), (mx + 25.0, mz + 3.6), (mx - 4.0, mz + 3.6)], 2.5, 3),
                   LOWER_HALF_W - 1.2, LOWER_HALF_W + 0.2, F, "Steel_black")
    boolean(bar, arm, "UNION")
    # зуб входит через окно шахты в паз на левой стенке магазина
    tooth = box("mag_catch_tooth", mx + 17.0, mx + 23.0, WELL_IN_HALF_W - 1.6, LOWER_HALF_W - 1.0, mz - 2.0, mz + 2.0, F, "Steel_black")
    boolean(bar, tooth, "UNION")
    finish(bar, w=0.25, seg=2, angle=35)
    o["mag_catch"] = bar
    return o


def bolt_catch(F):
    """Затворная задержка: рычаг на левом боку (нижняя лопатка — поставить на задержку, верхняя — отпустить),
    сверху поперечный зуб в путь затвора; поворот вокруг оси вдоль X."""
    bx, by, bz = BOLT_CATCH_PIVOT
    # поперечное сечение (y, z): наружная стойка, сверху загиб внутрь к зубу
    prof = fillet([(by - 1.2, bz - 4.6), (by + 1.6, bz - 4.6), (by + 2.0, bz - 2.0), (by + 1.8, bz + 9.5), (by + 0.4, bz + 11.0),
                   (8.0, bz + 11.0), (7.4, bz + 14.6), (6.0, bz + 14.6), (5.6, bz + 9.2), (by - 1.4, bz + 8.4), (by - 1.4, bz + 2.0)],
                  [0.8, 1.2, 2.0, 1.5, 1.0, 0.5, 0.6, 0.5, 1.0, 1.0, 1.0], 3)
    bc = prism_yz("Bolt_catch", prof, bx - 7.4, bx + 7.4, F, "Steel_black")
    # зуб уже стойки: подрезаем по X спереди и сзади
    for x0, x1 in ((bx - 10, bx - 3.2), (bx + 3.2, bx + 10)):
        boolean(bc, box("cut_bc_tooth", x0, x1, 4.0, by - 2.0, bz + 7.0, bz + 20, F))
    # лопатки снаружи: нижняя и верхняя, рифлёные
    for nm, z0, z1 in (("low", bz - 4.8, bz - 0.8), ("high", bz + 3.5, bz + 10.5)):
        pad = prism_xz(f"bc_pad_{nm}", fillet([(bx - 7.2, z0), (bx + 7.2, z0), (bx + 7.2, z1), (bx - 7.2, z1)], 2.0, 3),
                       by + 0.8, by + 3.0, F, "Steel_black")
        boolean(bc, pad, "UNION")
        for k in range(int((z1 - z0) / 1.8)):
            zz = z0 + 1.0 + k * 1.8
            boolean(bc, box(f"bc_ser{nm}{k}", bx - 8.5, bx + 7.5, by + 2.5, by + 4.6, zz - 0.4, zz + 0.4, F))
    boolean(bc, cyl("cut_bc_hole", bx - 20, bx + 20, 1.2, F, seg=16, cy=by, cz=bz, axis="X"))
    finish(bc, w=0.25, seg=2, angle=35)
    return bc
