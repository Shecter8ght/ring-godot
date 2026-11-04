# ПП по мотивам KRISS Vector: управление подвижными частями. Пустышка SMG03_Controls — свойства 0…1:
#   charging_handle — рукоятка заряжания назад (тянет затвор; при стрельбе не ходит)
#   bolt            — затвор назад сам (выстрел); рукоятка при этом стоит
#   trigger         — выжим спуска (на «предохранителе» не идёт)
#   safety          — 1 предохранитель включён, 0 — огонь (флажки с обеих сторон на одной оси)
#   selector        — переводчик огня: 0 «ОД», 0.5 «2», 1 «АВ» (флажки с обеих сторон на одной оси)
#   mag_release     — лопатки защёлки нажаты; mag_out — магазин вниз из шахты вдоль своей оси
#   bolt_release    — кнопка затворной задержки нажата
#   front_sight, rear_sight — прицельные подняты (1) / сложены (0)
#   stock_fold      — приклад сложен вправо (1); stock_latch — кнопка защёлки приклада нажата
#   side_buttons    — рифлёные кнопки левой площадки нажаты
#   mag30           — 1: стоит магазин на 30 (коллекция Magazine_30), 0 — на 13
import math
import bpy
from mathutils import Vector
from lib import MM, empty, set_parent
from part_bolt import BOLT_TRAVEL, CH_TRAVEL
from part_receiver import mag_frame
from part_stock import HINGE_X, HINGE_Y

PROPS = ["charging_handle", "bolt", "trigger", "safety", "selector", "mag_release", "mag_out", "bolt_release",
         "front_sight", "rear_sight", "stock_fold", "stock_latch", "side_buttons", "mag30"]
DEFAULTS = {"front_sight": 1.0, "rear_sight": 1.0}
SAFETY_DEG = 55.0
SELECTOR_DEG = 60.0
MAG_DROP = 150.0


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


def build(ctx):
    R = ctx["coll"]["Rig"]
    root = empty("SMG03", (0, 0, 0), R, size=0.05, kind="ARROWS")
    ctrl = empty("SMG03_Controls", (-60.0, 0, 110.0), R, root, size=0.02, kind="CIRCLE")
    for k in PROPS:
        ctrl[k] = DEFAULTS.get(k, 0.0)
        ctrl.id_properties_ui(k).update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, step=1)
    # затвор и выбрасыватель — ход назад по X (рукоятка тянет затвор, затвор рукоятку — нет)
    bm = empty("Bolt_mover", (0, 0, 0), R, root, size=0.01)
    add_driver(bm, "location", 0, f"-max(bolt, charging_handle)*{BOLT_TRAVEL}*{MM}", ctrl, ["bolt", "charging_handle"])
    for n in ("Bolt", "Extractor", "Extractor_pin"):
        if ob(n):
            set_parent(ob(n), bm)
    cm = empty("Charging_handle_mover", (0, 0, 0), R, root, size=0.008)
    add_driver(cm, "location", 0, f"-charging_handle*{CH_TRAVEL}*{MM}", ctrl, ["charging_handle"])
    for n in ("Charging_handle", "Charging_handle_slider"):
        if ob(n):
            set_parent(ob(n), cm)
    # спуск (начало координат — на оси): задняя кромка назад, на предохранителе не идёт
    if ob("Trigger"):
        add_driver(ob("Trigger"), "rotation_euler", 1, "-radians(11.0)*trigger*(1.0 if safety<0.5 else 0.0)", ctrl,
                   ["trigger", "safety"])
    for n in ("Safety_L", "Safety_R"):
        if ob(n):
            add_driver(ob(n), "rotation_euler", 1, f"-radians({SAFETY_DEG})*safety", ctrl, ["safety"])
    for n in ("Selector_L", "Selector_R"):
        if ob(n):
            add_driver(ob(n), "rotation_euler", 1, f"radians({SELECTOR_DEG})*selector", ctrl, ["selector"])
    for n, s in (("Mag_release_L", -1), ("Mag_release_R", 1)):
        if ob(n):
            add_driver(ob(n), "location", 1, f"{ob(n).location.y}+{s}*1.3*{MM}*mag_release", ctrl, ["mag_release"])
    if ob("Bolt_release"):
        add_driver(ob("Bolt_release"), "location", 1, f"1.3*{MM}*bolt_release", ctrl, ["bolt_release"])
    for n in ("Side_button_front", "Side_button_rear"):
        if ob(n):
            add_driver(ob(n), "location", 1, f"-0.4*{MM}*side_buttons", ctrl, ["side_buttons"])
    # прицельные: целик складывается вперёд (+Y-поворот), мушка — назад
    if ob("Rear_sight_leaf"):
        add_driver(ob("Rear_sight_leaf"), "rotation_euler", 1, "radians(90.0)*(1.0-rear_sight)", ctrl, ["rear_sight"])
    if ob("Front_sight_leaf"):
        add_driver(ob("Front_sight_leaf"), "rotation_euler", 1, "-radians(90.0)*(1.0-front_sight)", ctrl, ["front_sight"])
    # магазины: вниз вдоль своей оси; видимость 13 / 30 — по mag30
    up, fwd = mag_frame()
    mm = empty("Magazine_mover", (0, 0, 0), R, root, size=0.01)
    for i, ax in enumerate("xyz"):
        add_driver(mm, "location", i, f"-mag_out*{MAG_DROP}*{MM}*{up[i]:.6f}", ctrl, ["mag_out"])
    for o in list(bpy.data.objects):
        if o.name.startswith(("Magazine13", "Magazine30")) and o.parent is None:
            set_parent(o, mm)
            is30 = o.name.startswith("Magazine30")
            for path in ("hide_viewport", "hide_render"):
                add_driver(o, path, None, "mag30<0.5" if is30 else "mag30>=0.5", ctrl, ["mag30"])
    # приклад: складывается вправо вокруг вертикальной оси шарнира; кнопка защёлки — внутрь
    sp = empty("Stock_pivot", (HINGE_X, HINGE_Y, 30.0), R, root, size=0.01)
    add_driver(sp, "rotation_euler", 2, "radians(180.0)*stock_fold", ctrl, ["stock_fold"])
    for n in ("Stock_body", "Stock_buttplate", "Stock_latch"):
        if ob(n):
            set_parent(ob(n), sp)
    for o in list(bpy.data.objects):
        if o.name.startswith("Stock_screw") and o.parent is None:
            set_parent(o, sp)
    if ob("Stock_latch"):
        add_driver(ob("Stock_latch"), "location", 1, f"{ob('Stock_latch').location.y}-1.5*{MM}*stock_latch", ctrl,
                   ["stock_latch"])
    bpy.context.view_layer.update()
    return {"root": root, "ctrl": ctrl}
