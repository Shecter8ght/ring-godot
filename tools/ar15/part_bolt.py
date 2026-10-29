# AR-15: затворная группа (рама с газовым ключом, затвор с семью боевыми упорами, выбрасыватель, отражатель,
# кулачковая ось, ударник со шпилькой) и рукоятка заряжания с двумя защёлками (амби).
# В положении «заперто»: зеркало затвора x=0, передний торец рамы −9, задний −176; кулачковая ось −28 (под газовой
# трубкой), ключ −36…−84 (выпускные отверстия за хвостом затвора), головка ударника −84 (сюда бьёт курок).
import math
import bpy
from lib import (MM, UPPER_REAR, GAS_Z, fillet, arc_pts, prism_xz, prism_yz, prism_xy, box, cyl, lathe, boolean, finish,
                 auto_sharp, apply_transform, material)
from part_upper import CHANNEL_HALF_W, CHANNEL_Z, RAIL_BASE

CARRIER_R = 12.3
CARRIER_FRONT = -14.5        # упирается в задний торец муфты ствола
EXT_ANGLE = -22.5            # выбрасыватель справа сверху, на месте упора
CARRIER_REAR = UPPER_REAR
CAM_X = -28.0
KEY_X = (-84.0, -36.0)
BOLT_TAIL = -58.0
FP_HEAD = -84.0
CH_FRONT = -33.0            # передний зацеп рукоятки — перед носиком ключа
CH_REAR = UPPER_REAR - 15.0
CH_WING_Y = 32.0            # размах крыльев Т-ручки (±): крупная амби-рукоятка (было ±25.5)
CH_CENTER_HW = 16.5         # полуширина средней плиты Т-ручки (пол под осями рычагов)


def build(ctx):
    B = ctx["coll"]["Bolt_group"]
    H = ctx["coll"]["Charging_handle"]
    o = {}
    # --- рама ---
    car = cyl("Bolt_carrier", CARRIER_REAR, CARRIER_FRONT, CARRIER_R, B, "Steel_nitride", seg=64, ch=0.8)
    # канал затвора спереди, камера расширения за хвостом затвора
    boolean(car, cyl("cut_bolt_bore", BOLT_TAIL - 12.0, CARRIER_FRONT + 2, 6.9, B, seg=48))
    boolean(car, cyl("cut_fp_bore", FP_HEAD - 6, BOLT_TAIL - 10, 3.0, B, seg=24))
    # снизу — паз под курок (курок проходит к головке ударника)
    boolean(car, box("cut_ham_slot", FP_HEAD - 14.0, FP_HEAD + 8.0, -5.2, 5.2, -CARRIER_R - 2, -1.5, B))
    boolean(car, box("cut_ham_face", FP_HEAD - 14.0, FP_HEAD + 0.6, -4.2, 4.2, -CARRIER_R - 2, 3.6, B))
    # газоотводные окна на правом боку рамы (выход газа из камеры за затвором)
    for xv in (-66.0, -59.0):
        boolean(car, cyl(f"cut_vent{xv}", -CARRIER_R - 3, -2.0, 1.5, B, seg=20, cy=xv, cz=2.6, axis="Y"))
    # спереди снизу выемка над магазином: по губкам и верхнему патрону идёт только затвор
    boolean(car, box("cut_mag_relief", -58.0, CARRIER_FRONT + 2, -12.8, 12.8, -CARRIER_R - 2, -5.0, B))
    # задняя часть снизу срезана (рама скользит по курку и взводит его)
    boolean(car, box("cut_tail_flat", CARRIER_REAR - 2, FP_HEAD - 12.0, -20, 20, -CARRIER_R - 2, -CARRIER_R + 1.4, B))
    # правая сторона: плоскость окна выброса и насечки (у «гладкого» ресивера насечки остаются на раме)
    boolean(car, box("cut_port_face", -74.0, CARRIER_FRONT - 2.0, -CARRIER_R - 2, -CARRIER_R + 1.6, -6.0, 8.5, B))
    # насечки досылателя — точно под его собачкой (её кончик при нажатии в x ≈ −140, 49.5° от верха к правому боку)
    for k in range(9):
        xx = -151.9 + k * 3.2
        c = box(f"cut_fa_ser{k}", xx - 0.9, xx + 0.9, -3.4, 3.4, CARRIER_R - 1.1, CARRIER_R + 2.0, B)
        c.rotation_euler = (math.radians(49.5), 0, 0)
        apply_transform(c)
        boolean(car, c)
    # кулачковый паз сверху: криволинейная прорезь (поворот затвора на 22.5°)
    slot = []
    for k in range(9):
        t = k / 8
        slot.append((CAM_X - 4.0 - 9.5 * t, 3.6 * math.sin(math.radians(90 * t)) - 3.6))
    pts = [(x, y + 3.3) for x, y in slot] + [(x, y - 3.3) for x, y in reversed(slot)]
    boolean(car, prism_xy("cut_cam_slot", fillet(pts, [3.0] + [0] * 7 + [3.0, 3.0] + [0] * 7 + [3.0], 4), 7.0, 20.0, B))
    # отверстие шпильки ударника слева
    boolean(car, cyl("cut_fp_pin", -20, 20, 1.15, B, seg=16, cy=FP_HEAD + 8.0, cz=1.5, axis="Y"))
    # площадка ключа сверху (плоская посадочная)
    boolean(car, box("cut_key_seat", KEY_X[0] - 1.0, KEY_X[1] + 1.0, -5.0, 5.0, CARRIER_R - 1.2, CARRIER_R + 3, B))
    finish(car, w=0.35, seg=2, angle=35)
    o["carrier"] = car
    # --- газовый ключ с двумя винтами ---
    kx0, kx1 = KEY_X
    key_prof = fillet([(kx0, CARRIER_R - 1.2), (kx1 - 5.0, CARRIER_R - 1.2), (kx1, GAS_Z - 3.2), (kx1, GAS_Z + 3.2),
                       (kx1 - 7.0, RAIL_BASE - 0.6), (kx0 + 3.0, RAIL_BASE - 0.6), (kx0, RAIL_BASE - 3.0)], [1, 2, 1, 1.5, 1.5, 2, 1], 3)
    key = prism_xz("Gas_key", key_prof, -4.7, 4.7, B, "Steel_nitride")
    boolean(key, cyl("cut_key_bore", kx1 - 26.0, kx1 + 2, 2.45, B, seg=20, cz=GAS_Z))
    for xs in (kx0 + 10.0, kx0 + 26.0):
        boolean(key, cyl("cut_key_cb", RAIL_BASE - 3.4, RAIL_BASE + 1, 3.0, B, seg=24, cy=xs, cz=0, axis="Z"))
    finish(key, w=0.3, seg=2, angle=35)
    o["key"] = key
    for i, xs in enumerate((kx0 + 10.0, kx0 + 26.0)):
        sc = cyl(f"Gas_key_screw{i}", CARRIER_R - 1.0, RAIL_BASE - 3.3, 2.6, B, "Steel_black", seg=24, cy=xs, cz=0, axis="Z", ch=0.3)
        # шестигранник под ключ
        hexa = prism_xy("cut_hex", [(xs + 1.25 * math.cos(math.radians(60 * k)), 1.25 * math.sin(math.radians(60 * k))) for k in range(6)],
                        RAIL_BASE - 5.0, RAIL_BASE, B)
        boolean(sc, hexa)
        # кернение кромки ключа у винта (следы чеканки)
        o[f"key_screw{i}"] = sc
    # --- затвор ---
    bolt = lathe("Bolt", [(BOLT_TAIL, 0.0), (BOLT_TAIL, 5.6), (BOLT_TAIL + 1.0, 6.6), (-50.0, 6.6), (-50.0, 6.85), (-38.0, 6.85),
                          (-38.0, 6.6), (-14.0, 6.6), (-13.0, 6.2), (-9.0, 6.2), (-8.0, 7.4), (-0.6, 7.4), (0.0, 6.8), (0.0, 0.0)],
                 B, "Steel_nitride", seg=64)
    # три газовых кольца
    for k in range(3):
        xx = -55.5 + k * 1.9
        boolean(bolt, lathe("cut_ring", [(xx - 0.45, 6.0), (xx - 0.45, 7.2), (xx + 0.45, 7.2), (xx + 0.45, 6.0)], B, None, seg=64))
    # боевые упоры: 7 + выбрасыватель на месте восьмого; пазы между ними
    for k in range(8):
        a = 45.0 * k
        c = box("cut_lug", -8.6, 0.5, -1.55, 1.55, 6.6, 9.0, B)
        c.rotation_euler = (math.radians(a), 0, 0)
        apply_transform(c)
        boolean(bolt, c)
    # чашка зеркала и канал ударника, отверстие кулачковой оси
    boolean(bolt, lathe("cut_cup", [(-1.3, 0.0), (-1.3, 4.85), (0.6, 4.85), (0.6, 0.0)], B, None, seg=48))
    boolean(bolt, cyl("cut_fp", BOLT_TAIL - 2, 1, 1.1, B, seg=16))
    boolean(bolt, cyl("cut_cam", -20, 20, 2.9, B, seg=24, cy=CAM_X, cz=0, axis="Z"))
    # прорезь выбрасывателя справа сверху и отверстие отражателя
    ce = box("cut_ext", -21.0, 1.0, -9.0, -3.4, -1.9, 1.9, B)
    ce.rotation_euler = (math.radians(EXT_ANGLE), 0, 0)
    apply_transform(ce)
    boolean(bolt, ce)
    boolean(bolt, lathe("cut_ejector", [(-6.0, 0.0), (-6.0, 1.15), (1.0, 1.15), (1.0, 0.0)], B, None, seg=16, cy=3.3, cz=-1.9))
    auto_sharp(bolt, 35)
    o["bolt"] = bolt
    # в системе «выбрасыватель на −Y»: потом поворот на EXT_ANGLE вместе с пазом
    ext = box("Extractor", -20.5, -8.6, -6.5, -4.9, -1.75, 1.75, B, "Steel_nitride")
    lug = box("ext_front", -8.6, 0.0, -7.35, -4.9, -1.5, 1.5, B, "Steel_nitride")
    boolean(ext, lug, "UNION")
    claw = prism_xy("ext_claw", [(-1.25, -7.35), (0.0, -7.35), (0.0, -5.0), (-0.4, -4.3), (-1.25, -4.3)], -1.3, 1.3, B, "Steel_nitride")
    boolean(ext, claw, "UNION")
    boolean(ext, cyl("cut_ext_pin", -20, 20, 0.9, B, seg=12, cy=-15.0, cz=0, axis="Z"))
    ext.rotation_euler = (math.radians(EXT_ANGLE), 0, 0)
    apply_transform(ext)
    finish(ext, w=0.2, seg=2, angle=35)
    o["extractor"] = ext
    o["ejector"] = lathe("Ejector", [(-1.2, 0.0), (-1.2, 1.05), (0.2, 1.05), (0.4, 0.8), (0.4, 0.0)], B, "Steel_bare", seg=16, cy=3.3, cz=-1.9)
    # кулачковая ось: цилиндр через затвор, квадратная головка сверху (едет в пазу рамы и ресивера)
    cp = cyl("Cam_pin", -2.0, CARRIER_R + 1.4, 2.8, B, "Steel_bare", seg=24, cy=CAM_X, cz=0, axis="Z")
    head = box("cam_head", CAM_X - 3.2, CAM_X + 3.2, -3.2, 3.2, CARRIER_R - 1.5, CARRIER_R + 1.6, B, "Steel_bare")
    boolean(cp, head, "UNION")
    finish(cp, w=0.4, seg=2, angle=35)
    o["cam_pin"] = cp
    # ударник: игла у зеркала, фланец, хвост — головка в −84
    o["firing_pin"] = lathe("Firing_pin", [(FP_HEAD, 0.0), (FP_HEAD, 2.4), (FP_HEAD + 1.0, 2.9), (FP_HEAD + 4.0, 2.9), (FP_HEAD + 4.0, 2.2),
                                           (-61.0, 2.2), (-60.0, 2.9), (-57.0, 2.9), (-56.5, 1.6), (-2.0, 1.05), (-0.6, 0.8),
                                           (-0.2, 0.5), (-0.2, 0.0)], B, "Steel_bare", seg=24)
    o["fp_pin"] = cyl("Firing_pin_retainer", -CARRIER_R + 0.6, CARRIER_R + 0.6, 1.1, B, "Steel_black", seg=12,
                      cy=FP_HEAD + 8.0, cz=1.5, axis="Y", ch=0.2)
    # --- рукоятка заряжания (амби, защёлки на обеих сторонах) ---
    o.update(charging_handle(H))
    return o


def _mirror(pts, s):
    """Контур рычага (вид сверху) для стороны s: зеркально по Y с сохранением обхода."""
    q = [(x, y * s) for x, y in pts]
    return q if s > 0 else list(reversed(q))


def charging_handle(H):
    """Рукоятка заряжания: тяга с зацепом за носик ключа и Т-ручка; крылья Т-ручки — сами рычаги-защёлки (амби, как у
    «больших» рукояток: широкие, с двумя сквозными окнами каждое). Рычаг вращается на оси у внутреннего края,
    его крючок спереди цепляет задний торец ресивера."""
    o = {}
    z0, z1 = RAIL_BASE + 0.1, CHANNEL_Z[1] - 0.2
    hw = CHANNEL_HALF_W - 0.3
    r = CH_REAR
    bar = prism_xz("Charging_handle", fillet([(CH_FRONT, z0), (r + 8.0, z0), (r + 8.0, z1), (CH_FRONT, z1)], [0.6, 0, 0, 0.6], 2),
                   -hw, hw, H, "Alu_anodized")
    # передний зацеп вниз (тянет ключ за носик)
    hook = prism_xz("ch_hook", fillet([(CH_FRONT, z0 + 0.5), (CH_FRONT + 5.0, z0 + 0.5), (CH_FRONT + 5.0, GAS_Z + 3.6), (CH_FRONT, GAS_Z + 3.6)],
                                      [0, 0, 0.8, 0.8], 2), -hw + 1.6, hw - 1.6, H, "Alu_anodized")
    boolean(bar, hook, "UNION")
    # облегчающий паз снизу по длине
    boolean(bar, box("cut_ch_under", CH_FRONT + 10.0, r + 30.0, -hw + 1.6, hw - 1.6, z0 - 1, z0 + 2.4, H))
    # средняя плита Т-ручки между рычагами: пол под осями рычагов, сверху — два винта
    center = prism_xy("ch_center", fillet([(r + 10.0, -CH_CENTER_HW), (r + 10.0, CH_CENTER_HW), (r - 7.5, CH_CENTER_HW),
                                           (r - 7.5, -CH_CENTER_HW)], [3.0, 3.0, 4.0, 4.0], 4), z0 - 2.0, z1 + 3.4, H, "Alu_anodized")
    boolean(bar, center, "UNION")
    # рифление на задней грани плиты
    for k in range(5):
        yy = -6.0 + k * 3.0
        boolean(bar, box(f"cut_ch_ser{k}", r - 9.0, r - 6.6, yy - 0.7, yy + 0.7, z0 - 3, z1 + 5, H))
    # гнёзда рычагов над полом и гнёзда их осей в полу; перед осью стенка гнезда скошена внутрь — рычаг при повороте
    # на 14° уводит внутренний край к тяге
    for s in (-1, 1):
        bay = [(r - 9.0, 8.4), (r + 3.0, 8.4), (r + 10.2, 7.15), (r + 10.2, 40.0), (r - 9.0, 40.0)]
        boolean(bar, prism_xy(f"cut_latch_bay{s}", _mirror(bay, s), z0 + 0.6, z1 + 4, H))
        boolean(bar, cyl(f"cut_latch_pin{s}", z0 - 1.0, z0 + 1.0, 1.02, H, seg=12, cy=r + 2.5, cz=11.5 * s, axis="Z"))
    # винты плиты (головки с шестигранником)
    for yy in (-4.4, 4.4):
        boolean(bar, cyl("ch_screw", z1 + 3.0, z1 + 3.9, 2.1, H, "Alu_anodized", seg=24, cy=r + 1.2, cz=yy, axis="Z", ch=0.3), "UNION")
        hexa = prism_xy("cut_ch_screw_hex", [(r + 1.2 + 1.05 * math.cos(math.radians(60 * k + 30)), yy + 1.05 * math.sin(math.radians(60 * k + 30)))
                                            for k in range(6)], z1 + 3.2, z1 + 4.5, H)
        boolean(bar, hexa)
    finish(bar, w=0.5, seg=2, angle=35)
    o["handle"] = bar
    # рычаги-крылья: внутренний край у оси, спереди крючок за торец ресивера, наружу — крыло до ±CH_WING_Y
    # с двумя сквозными окнами и рифлением на конце
    outline = [(r - 0.5, 9.4), (r + 3.5, 9.4), (r + 10.5, 9.9), (r + 13.5, 11.6), (r + 13.5, 13.4), (r + 10.8, 13.4),
               (r + 10.2, 17.0), (r + 8.8, 24.0), (r + 6.4, 29.6), (r + 3.0, CH_WING_Y), (r - 1.6, CH_WING_Y), (r - 5.2, 29.6),
               (r - 7.4, 24.0), (r - 7.2, 18.0), (r - 4.6, 13.6), (r - 2.6, 11.0)]
    rad = [1.0, 0.4, 0.6, 0.8, 0.6, 0.6, 2.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 2.0, 2.0, 1.4]
    win_in = [(r - 3.6, 16.2), (r + 6.8, 16.2), (r + 5.4, 22.4), (r - 4.4, 22.4)]
    win_out = [(r - 3.4, 24.8), (r + 4.6, 24.8), (r - 0.4, 29.0), (r - 2.8, 29.0)]
    for s, nm in ((1, "CH_latch_L"), (-1, "CH_latch_R")):
        pts = _mirror(fillet(outline, rad, 3), s)
        lat = prism_xy(nm, pts, z0 + 0.8, z1 + 3.0, H, "Alu_anodized")
        for k, (w, rr) in enumerate(((win_in, 1.6), (win_out, 1.0))):
            boolean(lat, prism_xy(f"cut_{nm}_win{k}", _mirror(fillet(w, rr, 4), s), z0 - 1, z1 + 5, H))
        # ось рычага
        boolean(lat, cyl(f"cut_{nm}_pivot", z0 - 1, z1 + 5, 1.05, H, seg=12, cy=r + 2.5, cz=11.5 * s, axis="Z"))
        # рифление поперёк конца крыла
        for k, yy in enumerate((29.7, 30.9)):
            boolean(lat, box(f"{nm}_ser{k}", r - 4.6, r + 5.6, (yy - 0.3) * s if s > 0 else (-yy - 0.3), (yy + 0.3) if s > 0 else (-yy + 0.3),
                             z1 + 2.5, z1 + 4, H))
        finish(lat, w=0.6, seg=2, angle=35)
        o[nm] = lat
        o[nm + "_pin"] = cyl(nm + "_pin", z0 + 0.5, z1 + 3.2, 1.0, H, "Steel_black", seg=12, cy=r + 2.5, cz=11.5 * s, axis="Z", ch=0.2)
    return o
