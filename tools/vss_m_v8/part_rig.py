# ВСС-М v8: иерархия, оси и управление. Пустышка VSS_Controls — свойства 0…1:
#   bolt_pull   — отвод затворной рамы (74 мм; при включённом предохранителе — упор у его выступа, 58 мм)
#   trigger     — выжим спуска (12°; при предохранителе не идёт)
#   safety      — предохранитель (0 «огонь», 1 «предохранитель» — рычаг вверх на 5° до зуба козырька)
#   selector    — переводчик-ползун за спуском (0 одиночный — выступает справа, 1 автоматический — слева)
#   mag_catch   — нажатие защёлки (8°)
#   mag_out     — снятие магазина: поворот вокруг переднего зацепа (0…0.5), затем вниз (0.5…1)
#   sight_range — секторный прицел: хомутик вперёд, лист вверх
#   suppressor_off — глушитель вместе с муфтой снимается вперёд
# Затвор: свободный ход рамы 6 мм, поворот −30° на участке 6…14 мм, дальше идёт с рамой (постановочно).
import math
import bpy
from lib import MM, BORE_Z, SAFETY_PIVOT, SAFETY_TRAVEL_DEG, SEL_TRAVEL, SEL_X0, SEL_X1, SEL_Z0, SEL_Z1, empty, set_parent, set_origin

TRAVEL = 74.0
TRAVEL_SAFE = 58.0


def add_driver(obj, path, index, expr, ctrl, props):
    fc = obj.driver_add(path, index)
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


def build(ctx):
    P = ctx["parts"]
    R = ctx["coll"]["Rig"]
    root = empty("VSS_M_v8", (0, 0, 0), R, size=0.05, kind="ARROWS")
    ctrl = empty("VSS_Controls", (400.0, 0, 80.0), R, root, size=0.02, kind="CIRCLE")
    props = {"bolt_pull": 0.0, "trigger": 0.0, "safety": 0.0, "selector": 0.0, "mag_catch": 0.0, "mag_out": 0.0,
             "sight_range": 0.0, "suppressor_off": 0.0}
    for k, v in props.items():
        ctrl[k] = v
        ui = ctrl.id_properties_ui(k)
        ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, step=1)

    def static(objs, parent):
        for o in objs:
            if o is not None and o.parent is None:
                set_parent(o, parent)

    rec = P["receiver"]
    receiver_static = [o for o in bpy.data.collections["Receiver"].objects]
    static(receiver_static, root)
    static(list(bpy.data.collections["Stock"].objects), root)

    # --- затворная группа ---
    b = P["bolt"]
    carrier = empty("Bolt_carrier_mover", (465.0, 0, BORE_Z), R, root, size=0.012)
    for k in ("carrier", "plate", "web", "handle", "piston"):
        set_parent(b[k], carrier)
    set_parent(b["guide"], root); set_parent(b["ejector"], root); set_parent(b["rails"], root)
    travel = f"bolt_pull*({TRAVEL}-{TRAVEL - TRAVEL_SAFE}*safety)"
    add_driver(carrier, "location", 0, f"(465.0-{travel})*{MM}", ctrl, ["bolt_pull", "safety"])
    BOLT_X = 474.5
    bolt = empty("Bolt_mover", (BOLT_X, 0, BORE_Z), R, root, size=0.01)
    for k in ("bolt", "extractor", "firing_pin"):
        set_parent(b[k], bolt)
    t = f"({travel})"
    add_driver(bolt, "location", 0, f"({BOLT_X}-max(0.0,{t}-14.0))*{MM}", ctrl, ["bolt_pull", "safety"])
    add_driver(bolt, "rotation_euler", 0, f"-radians(30.0)*min(1.0,max(0.0,({t}-6.0)/8.0))", ctrl, ["bolt_pull", "safety"])
    # пружина сжимается от переднего конца: начало координат пружины — у заднего упора
    spr = b["spring"]
    set_origin(spr, (292.5, 0, 28.0))
    set_parent(spr, root)
    add_driver(spr, "scale", 0, f"(101.5-{t})/101.5", ctrl, ["bolt_pull", "safety"])

    # --- органы управления ---
    c = P["controls"]
    trig_p = empty("Trigger_pivot", (372.0, 0, -9.0), R, root, size=0.006)
    set_parent(c["trigger"], trig_p)
    add_driver(trig_p, "rotation_euler", 1, "radians(12.0)*trigger*(1.0-safety)", ctrl, ["trigger", "safety"])
    saf_p = empty("Safety_pivot", (SAFETY_PIVOT[0], 0, SAFETY_PIVOT[1]), R, root, size=0.006)
    set_parent(c["safety"], saf_p)
    add_driver(saf_p, "rotation_euler", 1, f"-radians({SAFETY_TRAVEL_DEG})*safety", ctrl, ["safety"])
    set_parent(c["safety_axis_L"], root)
    sel_p = empty("Selector_mover", ((SEL_X0 + SEL_X1) / 2, 0, (SEL_Z0 + SEL_Z1) / 2), R, root, size=0.005)
    set_parent(c["selector"], sel_p)
    add_driver(sel_p, "location", 1, f"{SEL_TRAVEL}*selector*{MM}", ctrl, ["selector"])
    cat_p = empty("Magazine_catch_pivot", (408.2, 0, -38.0), R, root, size=0.006)
    set_parent(c["catch"], cat_p)
    add_driver(cat_p, "rotation_euler", 1, "-radians(8.0)*mag_catch", ctrl, ["mag_catch"])

    # --- магазин в оружии: поворот вокруг переднего зацепа, потом вниз ---
    m10 = P["magazine"]["10"]["body"]
    mag_p = empty("Magazine_pivot", (478.0, 0, -8.0), R, root, size=0.008)
    set_parent(m10, mag_p)
    add_driver(mag_p, "rotation_euler", 1, "-radians(16.0)*min(1.0,mag_out*2.0)", ctrl, ["mag_out"])
    mag_drop = m10
    add_driver(mag_drop, "location", 2, f"{m10.location.z}-90.0*{MM}*max(0.0,mag_out*2.0-1.0)", ctrl, ["mag_out"])
    m20 = P["magazine"]["20"]["body"]
    set_parent(m20, root)
    m20.location.y += 0.16          # для осмотра — рядом с оружием; на столе раскладывается сценой
    m30 = P["magazine"]["30"]["body"]
    set_parent(m30, root)
    m30.location.y += 0.30

    # --- перед: цевьё и ствол неподвижны, глушитель с муфтой и прицелами снимается вперёд ---
    f = P["front"]
    set_parent(f["handguard"], root); set_parent(f["barrel"], root); set_parent(f["swivel_lug"], root)
    sw_p = empty("Front_swivel_pivot", (560.5, 23.4, 7.0), R, root, size=0.004)
    set_parent(f["swivel"], sw_p)
    sup = empty("Suppressor_mount", (567.3, 0, BORE_Z), R, root, size=0.012)
    for o in bpy.data.collections["Suppressor"].objects:
        if o.parent is None:
            set_parent(o, sup)
    for o in bpy.data.collections["Rail_sleeve"].objects:
        if o.parent is None:
            set_parent(o, sup)
    add_driver(sup, "location", 0, f"(567.3+340.0*suppressor_off)*{MM}", ctrl, ["suppressor_off"])
    from part_front import SIGHT_DZ
    leaf_p = empty("Rear_sight_leaf_pivot", (633.0, 0, 39.5 + SIGHT_DZ), R, sup, size=0.005)
    set_parent(f["leaf"], leaf_p)
    set_parent(f["slider"], f["leaf"])
    # хомутик едет по сектору: подъём сектора под хомутиком / плечо до шарнира
    add_driver(leaf_p, "rotation_euler", 1, "((2.0+28.0*sight_range)/30.0)**2/(41.0-28.0*sight_range)", ctrl, ["sight_range"])
    sl = f["slider"]
    add_driver(sl, "location", 0, f"{sl.location.x}+28.0*{MM}*sight_range", ctrl, ["sight_range"])
    # проверочные положения в свойствах: сохранить исходные
    bpy.context.view_layer.update()
    return {"root": root, "ctrl": ctrl}
