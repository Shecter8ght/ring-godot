# ПП по мотивам KRISS Vector: управление подвижными частями. Пустышка SMG03_Controls — свойства 0…1:
#   charging_handle — рукоятка заряжания: 0…0.2 — откидывается влево на 90°, 0.2…1 — назад (тянет затвор; при стрельбе
#                     не ходит)
#   bolt            — затвор назад сам (выстрел); рукоятка при этом стоит
#   trigger         — выжим спуска (на «предохранителе» не идёт)
#   safety          — 1 предохранитель включён, 0 — огонь (флажки с обеих сторон на одной оси)
#   selector        — переводчик огня: 0 «ОД», 0.5 «2», 1 «АВ» (флажки с обеих сторон на одной оси)
#   mag_release     — лопатки защёлки нажаты; mag_out — магазин вниз из шахты вдоль своей оси
#   bolt_catch      — затвор на задержке: задний конец рычага задержки утоплен, затвор стоит сзади
#   bolt_release    — передний конец рычага задержки нажат: задержка снята, затвор уходит вперёд
#   front_sight, rear_sight — прицельные подняты (1) / сложены (0)
#   stock_fold      — приклад сложен вправо (1); stock_latch — кнопка защёлки приклада нажата
#   mag30           — 1: стоит магазин на 30 (коллекция Magazine_30), 0 — на 13
import math
import bpy
from mathutils import Vector
from lib import MM, empty, set_parent
from part_bolt import BOLT_TRAVEL, CH_TRAVEL, CH_TURN, CH_SWING
from part_controls import CATCH_DEG
from part_receiver import mag_frame
from part_stock import HINGE_X, HINGE_Y

PROPS = ["charging_handle", "bolt", "trigger", "safety", "selector", "mag_release", "mag_out", "bolt_catch",
         "bolt_release", "front_sight", "rear_sight", "stock_fold", "stock_latch", "mag30"]
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
    # ход рукоятки назад — после откидывания (доля CH_TURN); рукоятка выбирает зазор CH_TRAVEL − BOLT_TRAVEL до тяги,
    # потом тянет затвор; на задержке (bolt_catch) затвор стоит сзади, пока не нажат передний конец рычага (bolt_release)
    ch_t = f"max(0.0, (charging_handle-{CH_TURN})/{1.0 - CH_TURN})"
    add_driver(bm, "location", 0,
               f"-max(bolt*{BOLT_TRAVEL}, {ch_t}*{CH_TRAVEL}-{CH_TRAVEL - BOLT_TRAVEL}, "
               f"bolt_catch*(1.0-bolt_release)*{BOLT_TRAVEL}, 0.0)*{MM}", ctrl,
               ["bolt", "charging_handle", "bolt_catch", "bolt_release"])
    for n in ("Bolt", "Extractor", "Extractor_pin", "Firing_pin", "Firing_pin_retainer", "Bolt_arm_pin"):
        if ob(n):
            set_parent(ob(n), bm)
    cm = empty("Charging_handle_mover", (0, 0, 0), R, root, size=0.008)
    add_driver(cm, "location", 0, f"-{ch_t}*{CH_TRAVEL}*{MM}", ctrl, ["charging_handle"])
    for n in ("Charging_handle", "Charging_handle_slider", "Charging_handle_pin"):
        if ob(n):
            set_parent(ob(n), cm)
    # рычаг сначала откидывается влево на 90° на оси у заднего конца, потом едет назад
    if ob("Charging_handle"):
        add_driver(ob("Charging_handle"), "rotation_euler", 2,
                   f"radians({CH_SWING})*min(1.0, charging_handle/{CH_TURN})", ctrl, ["charging_handle"])
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
    # рычаг задержки — качалка на вертикальной оси: задний конец внутрь (+угол) — на задержке, передний внутрь (−угол) —
    # задержка снята
    if ob("Bolt_catch"):
        add_driver(ob("Bolt_catch"), "rotation_euler", 2,
                   f"radians({CATCH_DEG})*(bolt_catch*(1.0-bolt_release)-bolt_release)", ctrl,
                   ["bolt_catch", "bolt_release"])
    # прицельные: целик складывается вперёд (+Y-поворот), мушка — назад; сложены на 89° (лежат на упоре без касания)
    if ob("Rear_sight_leaf"):
        add_driver(ob("Rear_sight_leaf"), "rotation_euler", 1, "radians(89.0)*(1.0-rear_sight)", ctrl, ["rear_sight"])
    if ob("Front_sight_leaf"):
        add_driver(ob("Front_sight_leaf"), "rotation_euler", 1, "-radians(89.0)*(1.0-front_sight)", ctrl, ["front_sight"])
        # барабан высоты, маховичок и столбик мушки — отдельные детали на стойке
        for n in ("Front_sight_drum", "Front_sight_drum_wheel", "Front_sight_post"):
            if ob(n):
                set_parent(ob(n), ob("Front_sight_leaf"))
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
    for n in ("Stock_body", "Stock_buttplate", "Stock_buttplate_core", "Stock_latch"):
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
