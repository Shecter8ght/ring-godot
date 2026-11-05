# «Осока»: управление подвижными узлами. Пустышка OSOKA_Controls — свойства 0…1:
#   front_cap / rear_cap — крышка снята (до 0.5 — вдоль оси трубы, дальше — в сторону, влево)
#   launcher_detach      — пусковой механизм с источником питания отстёгнут от трубы (вниз)
#   power_out            — источник питания вынут из гнезда вдоль своей оси
#   lever                — рычаг «ИСХОДНОЕ» (0) → «НАКОЛ» (1): рукоятка вверх на оси спереди
#   trigger              — спуск выжат;  button — кнопка нажата;  plunger — толкатель за рукоятью нажат
#   front_sight / rear_sight — мушка / целик подняты (1) или сложены вниз-наружу (0)
#   dust_cover           — прямоугольная крышка сверху откинута вперёд
#   missile_out          — ракета выдвинута из трубы вперёд (смотреть отдельно; 1 — целиком перед трубой)
#   fins                 — стабилизаторы и рули раскрыты (как в полёте)
import math
import bpy
from mathutils import Vector
from lib import MM, empty, set_parent
import dims as D
import part_saddle
import part_launcher

PROPS = ["front_cap", "rear_cap", "launcher_detach", "power_out", "lever", "trigger", "button", "plunger",
         "front_sight", "rear_sight", "dust_cover", "missile_out", "fins"]
DEFAULTS = {"front_sight": 1.0, "rear_sight": 1.0}
CAP_TRAVEL = 140.0
CAP_SIDE = 150.0
DETACH = 95.0
POWER_TRAVEL = 115.0
TRIGGER_DEG = 10.0             # v06: ось качания выше (в раме над вырезом) — тот же ход пальца
SIGHT_FOLD_DEG = 80.0
DUST_DEG = 105.0
MISSILE_TRAVEL = 1800.0


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
    root = empty("OSOKA", (0, 0, 0), R, size=0.08, kind="ARROWS")
    ctrl = empty("OSOKA_Controls", (1300.0, 0, 170.0), R, root, size=0.03, kind="CIRCLE")
    for k in PROPS:
        ctrl[k] = DEFAULTS.get(k, 0.0)
        ctrl.id_properties_ui(k).update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, step=1)

    # крышки трубы — сдвиг вдоль оси
    fc = empty("Front_cap_mover", (0, 0, 0), R, root, size=0.01)
    # снятая крышка — вперёд и в сторону (влево), не на оси: ракету выдвигают при снятых крышках
    add_driver(fc, "location", 0, f"min(front_cap*2.0, 1.0)*{CAP_TRAVEL * 0.6}*{MM}", ctrl, ["front_cap"])
    add_driver(fc, "location", 1, f"max(front_cap*2.0-1.0, 0.0)*{CAP_SIDE}*{MM}", ctrl, ["front_cap"])
    for o in list(bpy.data.objects):
        if o.type == "MESH" and o.name.startswith("Front_cap"):
            set_parent(o, fc)
    rc = empty("Rear_cap_mover", (0, 0, 0), R, root, size=0.01)
    add_driver(rc, "location", 0, f"-min(rear_cap*2.0, 1.0)*{CAP_TRAVEL * 0.6}*{MM}", ctrl, ["rear_cap"])
    add_driver(rc, "location", 1, f"max(rear_cap*2.0-1.0, 0.0)*{CAP_SIDE}*{MM}", ctrl, ["rear_cap"])
    for o in list(bpy.data.objects):
        if o.type == "MESH" and o.name.startswith("Rear_cap"):
            set_parent(o, rc)

    # пусковой механизм целиком (с гнездом и источником питания) — вниз от трубы
    lm = empty("Launcher_mover", (0, 0, 0), R, root, size=0.02)
    add_driver(lm, "location", 2, f"-launcher_detach*{DETACH}*{MM}", ctrl, ["launcher_detach"])
    for coll_name in ("Launcher", "Power"):
        for o in list(ctx["coll"][coll_name].objects):
            if o.parent is None:
                set_parent(o, lm)

    # источник питания — вдоль своей оси
    import part_power
    c, ax, _m = part_power.frame()
    pm = empty("Power_mover", (0, 0, 0), R, lm, size=0.01)
    for i in range(3):
        if abs(ax[i]) > 1e-6:
            add_driver(pm, "location", i, f"power_out*{POWER_TRAVEL}*{MM}*{ax[i]:.6f}", ctrl, ["power_out"])
    if ob("Power_source"):
        set_parent(ob("Power_source"), pm)

    # рычаг: «накол» — рукоятка вверх-назад (поворот вокруг Y с минусом поднимает передний конец)
    if ob("Lever"):
        # ось спереди, рукоятка назад: поворот вокруг +Y на плюс поднимает задний конец (v05)
        add_driver(ob("Lever"), "rotation_euler", 1, f"radians({D.LEVER_TRAVEL_DEG})*lever", ctrl, ["lever"])
    # спуск: нижний конец назад
    if ob("Trigger"):
        add_driver(ob("Trigger"), "rotation_euler", 1, f"radians({TRIGGER_DEG})*trigger", ctrl, ["trigger"])
    if ob("Button_cap"):
        add_driver(ob("Button_cap"), "location", 1, f"-1.6*{MM}*button", ctrl, ["button"])
    if ob("Plunger"):
        add_driver(ob("Plunger"), "location", 1, f"-2.2*{MM}*plunger", ctrl, ["plunger"])

    # прицельные: складываются вдоль трубы на оси поперёк (Y) — мушка вперёд, целик назад (направление по источникам
    # не подтверждено — вопрос владельцу)
    if ob("Front_sight_leaf"):
        add_driver(ob("Front_sight_leaf"), "rotation_euler", 1, f"radians({SIGHT_FOLD_DEG})*(1.0-front_sight)", ctrl,
                   ["front_sight"])
    if ob("Rear_sight_leaf"):
        add_driver(ob("Rear_sight_leaf"), "rotation_euler", 1, f"-radians({SIGHT_FOLD_DEG})*(1.0-rear_sight)", ctrl,
                   ["rear_sight"])
        if ob("Rear_sight_indicator"):
            set_parent(ob("Rear_sight_indicator"), ob("Rear_sight_leaf"))
    # крышка сверху — откидывается вперёд на петле (передний край, ось Y)
    if ob("Dust_cover"):
        add_driver(ob("Dust_cover"), "rotation_euler", 1, f"radians({DUST_DEG})*dust_cover", ctrl, ["dust_cover"])

    # ракета: корень в трубе на X0; выдвигается вперёд; стабилизаторы и рули раскрываются
    mr = empty("Missile_root", (0, 0, 0), R, root, size=0.02, kind="SINGLE_ARROW")
    for o in list(ctx["coll"]["Missile"].objects):
        if o.parent is None:
            set_parent(o, mr)
    add_driver(mr, "location", 0, f"({D.MISSILE_X0}+missile_out*{MISSILE_TRAVEL})*{MM}", ctrl, ["missile_out"])
    for k in range(4):
        f = ob(f"Missile_fin_{k}")
        if f:
            add_driver(f, "rotation_euler", 0, "-radians(90.0)*fins", ctrl, ["fins"])
    if ob("Missile_rudder_top"):
        add_driver(ob("Missile_rudder_top"), "rotation_euler", 1, "-radians(90.0)*(1.0-fins)", ctrl, ["fins"])
    if ob("Missile_rudder_bottom"):
        add_driver(ob("Missile_rudder_bottom"), "rotation_euler", 1, "radians(90.0)*(1.0-fins)", ctrl, ["fins"])

    # остальное — под общий корень
    for o in list(bpy.data.objects):
        if o.parent is None and o is not root:
            set_parent(o, root)
    bpy.context.view_layer.update()
    return {"root": root, "ctrl": ctrl}
