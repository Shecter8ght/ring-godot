# AR-15: иерархия, оси и управление. Пустышка AR15_Controls — свойства 0…1:
#   forward_assist  — кнопка досылателя нажата (толкатель идёт вдоль своей оси к насечкам рамы)
#   charging_handle — рукоятка заряжания назад (тянет раму за ключ; ход как у рамы)
#   bolt_carrier    — рама назад сама по себе (выстрел, задержка затвора); рукоятка при этом стоит
#   hammer          — курок взведён (1) / спущен (0); рама при отходе взводит его сама
#   trigger         — выжим спуска (на «предохранителе» не идёт)
#   selector        — переводчик: 0 «предохранитель», 0.5 «одиночный», 1 «автоматический» (флажок вперёд → вверх → назад)
#   dust_cover      — крышка окна выброса открыта (открывается и сама, когда рама сдвинулась)
#   mag_catch       — кнопка защёлки нажата; mag_out — магазин вниз из шахты
#   bolt_catch      — затворная задержка поднята (держит затвор открытым)
#   ch_latch        — защёлки рукоятки заряжания нажаты
#   pivot_pin, takedown_pin — оси выдвинуты вправо; upper_open — верхний ресивер откинут на оси сборки
#   stock           — приклад выдвинут (6 положений через 0.2); stock_latch — рычаг фиксатора нажат
#   suppressor_off  — глушитель снят вперёд (собачка сначала поднимается с храповика муфты)
#   rear_sight, front_sight — прицелы подняты (1) / сложены (0); rear_aperture — диоптр перекинут на большое отверстие
# Затвор: свободный ход рамы BOLT_FREE, поворот на BOLT_ROT за BOLT_UNLOCK, дальше идёт с рамой.
import math
import bpy
from mathutils import Vector
from lib import (MM, FA_S, FA_D, FA_TRAVEL, CARRIER_TRAVEL, BOLT_FREE, BOLT_UNLOCK, BOLT_ROT, PIVOT_PIN, TAKEDOWN_PIN, SELECTOR, TRIGGER_PIN,
                 HAMMER_PIN, MAG_BUTTON, STOCK_TRAVEL, empty, set_parent, set_origin)
from part_upper import HINGE_Y, HINGE_Z
from part_lower import BOLT_CATCH_PIVOT
from part_bolt import CH_REAR

PROPS = ["forward_assist", "charging_handle", "bolt_carrier", "hammer", "trigger", "selector", "dust_cover", "mag_catch", "mag_out",
         "bolt_catch", "ch_latch", "pivot_pin", "takedown_pin", "upper_open", "stock", "stock_latch", "suppressor_off",
         "rear_sight", "front_sight", "rear_aperture"]
DEFAULTS = {"hammer": 1.0, "selector": 0.5, "rear_sight": 1.0, "front_sight": 1.0}
TRAVEL = f"(max(charging_handle, bolt_carrier)*{CARRIER_TRAVEL})"
HAMMER_COCK_DEG = 54.0
SPRING_LEN = 120.5          # возвратная пружина при запертом затворе
STOCK_LATCH_SIGN = 1.0
UPPER_OPEN_DEG = 32.0


def add_driver(obj, path, index, expr, ctrl, props):
    fc = obj.driver_add(path, index) if index is not None else obj.driver_add(path)
    drv = fc.driver
    drv.type = "SCRIPTED"
    for p in props:
        var = drv.variables.new()
        var.name = p
        var.type = "SINGLE_PROP"
        var.targets[0].id = ctrl
        var.targets[0].data_path = f'["{p}"]'
    drv.expression = expr
    return fc


def ob(name):
    return bpy.data.objects.get(name)


def coll_roots(name):
    c = bpy.data.collections.get(name)
    if c is None:
        return []
    out = []
    for o in c.all_objects:
        if o.parent is None:
            out.append(o)
    return out


def build(ctx):
    R = ctx["coll"]["Rig"]
    root = empty("AR15", (0, 0, 0), R, size=0.05, kind="ARROWS")
    ctrl = empty("AR15_Controls", (-60.0, 0, 90.0), R, root, size=0.02, kind="CIRCLE")
    for k in PROPS:
        ctrl[k] = DEFAULTS.get(k, 0.0)
        ui = ctrl.id_properties_ui(k)
        ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, step=1)

    # --- верхняя группа целиком откидывается на оси сборки ---
    px, pz = PIVOT_PIN
    upper_g = empty("Upper_group_pivot", (px, 0, pz), R, root, size=0.012)
    add_driver(upper_g, "rotation_euler", 1, f"radians({UPPER_OPEN_DEG})*upper_open", ctrl, ["upper_open"])
    lower_g = empty("Lower_group", (0, 0, 0), R, root, size=0.012)

    # затворная группа
    t = TRAVEL
    car = empty("Bolt_carrier_mover", (0, 0, 0), R, upper_g, size=0.01)
    add_driver(car, "location", 0, f"-{t}*{MM}", ctrl, ["charging_handle", "bolt_carrier"])
    for n in ("Bolt_carrier", "Gas_key", "Gas_key_screw0", "Gas_key_screw1", "Firing_pin_retainer"):
        if ob(n):
            set_parent(ob(n), car)
    bolt = empty("Bolt_mover", (0, 0, 0), R, upper_g, size=0.008)
    unlock = f"min(1.0,max(0.0,({t}-{BOLT_FREE})/{BOLT_UNLOCK}))"
    add_driver(bolt, "location", 0, f"-max(0.0,{t}-{BOLT_FREE + BOLT_UNLOCK})*{MM}", ctrl, ["charging_handle", "bolt_carrier"])
    add_driver(bolt, "rotation_euler", 0, f"radians({BOLT_ROT})*{unlock}", ctrl, ["charging_handle", "bolt_carrier"])
    for n in ("Bolt", "Extractor", "Ejector", "Cam_pin", "Firing_pin"):
        if ob(n):
            set_parent(ob(n), bolt)
    # рукоятка заряжания и её защёлки
    ch = empty("Charging_handle_mover", (0, 0, 0), R, upper_g, size=0.008)
    add_driver(ch, "location", 0, f"-charging_handle*{CARRIER_TRAVEL}*{MM}", ctrl, ["charging_handle"])
    if ob("Charging_handle"):
        set_parent(ob("Charging_handle"), ch)
    for s, nm in ((1, "CH_latch_L"), (-1, "CH_latch_R")):
        if not ob(nm):
            continue
        lp = empty(nm + "_pivot", (CH_REAR + 2.5, 11.5 * s, 25.0), R, ch, size=0.004)
        set_parent(ob(nm), lp)
        if ob(nm + "_pin"):
            set_parent(ob(nm + "_pin"), ch)
        add_driver(lp, "rotation_euler", 2, f"{-s}*radians(14.0)*ch_latch", ctrl, ["ch_latch"])
    # досылатель: толкатель вдоль оси корпуса
    if ob("Forward_assist"):
        fam = empty("Forward_assist_mover", FA_S, R, upper_g, size=0.005)
        set_parent(ob("Forward_assist"), fam)
        d = Vector(FA_D).normalized()
        for i in range(3):
            add_driver(fam, "location", i, f"{FA_S[i]*MM}+{d[i]*FA_TRAVEL*MM}*forward_assist", ctrl, ["forward_assist"])
    # пылезащитная крышка — на своей оси; открывается рукой или рамой
    cov = empty("Dust_cover_hinge", (0, HINGE_Y, HINGE_Z), R, upper_g, size=0.006)
    if ob("Dust_cover"):
        set_parent(ob("Dust_cover"), cov)
    add_driver(cov, "rotation_euler", 0, f"radians(112.0)*max(dust_cover,min(1.0,{t}/3.0))", ctrl,
               ["dust_cover", "charging_handle", "bolt_carrier"])
    # прочая верхняя группа: ресивер, ствол, цевьё, тормоз, глушитель, прицелы
    for cname in ("Upper", "Barrel", "Handguard", "Muzzle", "Sights"):
        for o in coll_roots(cname):
            set_parent(o, upper_g)
    sup = empty("Suppressor_mover", (0, 0, 0), R, upper_g, size=0.01)
    add_driver(sup, "location", 0, f"suppressor_off*220.0*{MM}", ctrl, ["suppressor_off"])
    for o in coll_roots("Suppressor"):
        set_parent(o, sup)
    if ob("Suppressor_latch"):
        add_driver(ob("Suppressor_latch"), "rotation_euler", 1, "radians(7.0)*min(1.0,suppressor_off*12.0)", ctrl, ["suppressor_off"])
    # складные прицелы: стойки на своих шарнирах (начала координат на осях)
    if ob("Rear_sight_leaf"):
        add_driver(ob("Rear_sight_leaf"), "rotation_euler", 1, "radians(90.0)*(1.0-rear_sight)", ctrl, ["rear_sight"])
    if ob("Front_sight_leaf"):
        add_driver(ob("Front_sight_leaf"), "rotation_euler", 1, "-radians(90.0)*(1.0-front_sight)", ctrl, ["front_sight"])
    if ob("Rear_sight_aperture"):
        add_driver(ob("Rear_sight_aperture"), "rotation_euler", 1, "radians(90.0)*rear_aperture", ctrl, ["rear_aperture"])

    # --- нижняя группа ---
    for cname in ("Lower", "Grip", "Stock"):
        for o in coll_roots(cname):
            set_parent(o, lower_g)
    # оси сборки и разборки — выдвигаются вправо (−Y)
    for nm, prop in (("Pivot_pin", "pivot_pin"), ("Takedown_pin", "takedown_pin")):
        if ob(nm):
            mv = empty(nm + "_mover", (0, 0, 0), R, lower_g, size=0.004)
            set_parent(ob(nm), mv)
            add_driver(mv, "location", 1, f"-{prop}*12.5*{MM}", ctrl, [prop])
    # курок: взводится назад; рама при отходе давит его вниз
    hx, hz = HAMMER_PIN
    hp = empty("Hammer_pivot", (hx, 0, hz), R, lower_g, size=0.006)
    if ob("Hammer"):
        set_parent(ob("Hammer"), hp)
    add_driver(hp, "rotation_euler", 1, f"-radians({HAMMER_COCK_DEG})*max(hammer,min(1.0,{t}/40.0))", ctrl,
               ["hammer", "charging_handle", "bolt_carrier"])
    # спуск (с разобщителем) — не идёт на «предохранителе»
    tx, tz = TRIGGER_PIN
    tp = empty("Trigger_pivot", (tx, 0, tz), R, lower_g, size=0.006)
    for n in ("Trigger", "Disconnector"):
        if ob(n):
            set_parent(ob(n), tp)
    add_driver(tp, "rotation_euler", 1, "radians(7.0)*trigger*(1.0 if selector>0.2 else 0.0)", ctrl, ["trigger", "selector"])
    # переводчик: флажок вперёд (предохранитель) → вверх (одиночный) → назад (автоматический)
    sx, sz = SELECTOR
    sp = empty("Selector_pivot", (sx, 0, sz), R, lower_g, size=0.006)
    for n in ("Selector", "Selector_lever_L", "Selector_lever_R"):
        if ob(n):
            set_parent(ob(n), sp)
    add_driver(sp, "rotation_euler", 1, "-radians(180.0)*selector", ctrl, ["selector"])
    # защёлка магазина: кнопка и тяга внутрь (+Y)
    mc = empty("Mag_catch_mover", (MAG_BUTTON[0], 0, MAG_BUTTON[1]), R, lower_g, size=0.005)
    for n in ("Mag_button", "Mag_catch"):
        if ob(n):
            set_parent(ob(n), mc)
    add_driver(mc, "location", 1, f"mag_catch*3.2*{MM}", ctrl, ["mag_catch"])
    # затворная задержка: поворот вокруг оси вдоль X — зуб поднимается в путь затвора
    bx, by, bz = BOLT_CATCH_PIVOT
    bp = empty("Bolt_catch_pivot", (bx, by, bz), R, lower_g, size=0.005)
    if ob("Bolt_catch"):
        set_parent(ob("Bolt_catch"), bp)
    add_driver(bp, "rotation_euler", 0, "-radians(8.0)*bolt_catch", ctrl, ["bolt_catch"])
    # магазин: вниз из шахты (все детали магазина — дети Magazine_body)
    mag = ob("Magazine_body")
    if mag is not None:
        mm = empty("Magazine_mover", (0, 0, 0), R, lower_g, size=0.01)
        set_parent(mag, mm)
        add_driver(mm, "location", 2, f"-mag_out*230.0*{MM}", ctrl, ["mag_out"])
    for o in coll_roots("Magazine"):
        if o.parent is None:
            set_parent(o, lower_g)
    # буфер идёт за рамой; пружина сжимается от заднего торца трубки (начало координат пружины там)
    if ob("Buffer"):
        bm = empty("Buffer_mover", (0, 0, 0), R, lower_g, size=0.008)
        set_parent(ob("Buffer"), bm)
        add_driver(bm, "location", 0, f"-{t}*{MM}", ctrl, ["charging_handle", "bolt_carrier"])
    sp_ = ob("Buffer_spring")
    if sp_ is not None:
        set_parent(sp_, lower_g)
        add_driver(sp_, "scale", 0, f"({SPRING_LEN}-{t})/{SPRING_LEN}", ctrl, ["charging_handle", "bolt_carrier"])
    # приклад: только по шести положениям (штифт фиксатора входит в отверстия направляющей через 16.8 мм)
    stb = ob("Stock_body")
    if stb is not None:
        smv = empty("Stock_mover", (0, 0, 0), R, lower_g, size=0.01)
        set_parent(stb, smv)
        add_driver(smv, "location", 0, f"-round(stock*5.0)/5.0*{STOCK_TRAVEL}*{MM}", ctrl, ["stock"])
        lat = ob("Stock_latch")
        if lat is not None:
            add_driver(lat, "rotation_euler", 1, f"{STOCK_LATCH_SIGN}*radians(6.0)*stock_latch", ctrl, ["stock_latch"])
        pin = ob("Stock_lock_pin")
        if pin is not None:
            add_driver(pin, "location", 2, f"{pin.location.z}-4.3*{MM}*stock_latch", ctrl, ["stock_latch"])
    # остальное без своего движения — к группам
    for cname, grp in (("Fire_control", lower_g), ("Lower", lower_g), ("Bolt_group", upper_g), ("Charging_handle", upper_g)):
        for o in coll_roots(cname):
            set_parent(o, grp)
    bpy.context.view_layer.update()
    return {"root": root, "ctrl": ctrl, "upper_group": upper_g, "lower_group": lower_g, "carrier": car}
