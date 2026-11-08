"""Надстройка: отсек экипажа с дверью, боковые отсеки под рольставнями (закрыты / подняты, внутри полки),
нижние отсеки снаружи рамы с задней аркой, полосы, задний насосный отсек, угловые стойки с фонарями,
подножка, лестница на крышу, белые рифлёные короба за кабиной."""
from __future__ import annotations

import crew as crew_mod
import lib
import shapes
import spec as S
from lib import s3d

HW = S.BODY_W / 2
L = S.BODY_BACK - S.BODY_FRONT
YM = (S.BODY_FRONT + S.BODY_BACK) / 2
FACE_IN = 0.012        # рольставня утоплена от борта


def locker_depth(k: int) -> float:
    """Задний отсек мельче: за ним во всю ширину насосный отсек."""
    return S.LOCKER_DEPTH if k < len(S.SHUTTERS) - 1 else 0.38


def hull():
    """Корпус: верх на раме во всю ширину, нижние отсеки снаружи рамы, арка задних колёс, ниши отсеков."""
    upper = s3d.box("body", S.BODY_W, L, S.BAND[0] - S.BODY_FLOOR)
    s3d.at(upper, y=YM, z=S.BODY_FLOOR)
    lockers = []
    for sx in (-1, 1):
        w = HW - S.LOCKER_IN
        lk = s3d.box("locker", w, L - 0.02, S.BODY_FLOOR - S.LOCKER_BOTTOM + 0.02)
        lockers.append(s3d.at(lk, x=sx * (S.LOCKER_IN + w / 2), y=YM - 0.01, z=S.LOCKER_BOTTOM))
    s3d.join(upper, lockers)
    tools = []
    for sx in (-1, 1):
        x0 = sx * S.LOCKER_IN - (0.0 if sx > 0 else 0.0)
        arch = s3d.cylinder("arch", 2 * S.ARCH_R_R, HW - S.LOCKER_IN + 0.10)
        tools.append(s3d.at(arch, x=sx * (S.LOCKER_IN - 0.02) if sx > 0 else -(HW + 0.08), y=S.YR, z=S.WHEEL_Z, ry=90))
        for k, (y0, y1, zb) in enumerate(S.SHUTTERS):
            dep = locker_depth(k)
            cav = s3d.box("locker_cav", dep + 0.05, (y1 - y0) - 0.08, S.SHUTTER_TOP - zb)
            tools.append(s3d.at(cav, x=sx * (HW - dep / 2 + 0.025), y=(y0 + y1) / 2, z=zb))
    # задний насосный отсек
    rs = S.REAR_SHUTTER
    pump = s3d.box("pump_cav", 2 * rs["x"] - 0.08, 0.60, rs["z1"] - rs["z0"])
    tools.append(s3d.at(pump, y=S.BODY_BACK - 0.30 + 0.05, z=rs["z0"]))
    s3d.cut(upper, tools)
    lib.paint_red(upper)
    return upper


def band():
    """Верхняя полоса (белая в отделке): чуть шире кузова, скруглённая кромка крыши, круглые габаритные огни."""
    b = s3d.box("top_band", S.BODY_W + 0.014, L + 0.014, S.BAND[1] - S.BAND[0])
    s3d.fillet(b, 0.03, edges="top")
    s3d.fillet(b, 0.012, edges="side")
    s3d.at(b, y=YM, z=S.BAND[0])
    lib.paint_white(b)
    out = [b]
    for sx in (-1, 1):
        for y in (-0.95, 0.85, 2.15, 3.45):
            lamp = s3d.cylinder("marker", 0.07, 0.02)
            lib.lens(lamp, "#f4f4ee")
            out.append(s3d.at(lamp, x=sx * (HW + 0.006), y=y, z=S.BAND[0] + 0.12, ry=90 * sx))
    return out


def rub_strips():
    """Полоса под рольставнями (белая, выступает) и обвод задней арки."""
    out = []
    zb, zt = S.RUB
    a0, a1 = S.YR - S.ARCH_R_R - 0.04, S.YR + S.ARCH_R_R + 0.04
    for sx in (-1, 1):
        for y0, y1 in ((S.BODY_FRONT + 0.02, a0), (a1, S.BODY_BACK - S.REAR_COL + 0.02)):
            prof = s3d.poly([(-sx * (HW - 0.002), zb), (-sx * (HW + 0.018), zb + 0.012), (-sx * (HW + 0.026), zb + 0.05),
                             (-sx * (HW + 0.026), zt - 0.03), (-sx * (HW + 0.016), zt), (-sx * (HW - 0.002), zt)],
                            fillet=[0, 0.006, 0.01, 0.01, 0.006, 0])
            st = s3d.extrude("rub_strip", prof, y1 - y0, on=lib.rear(y0))
            lib.paint_white(st)
            out.append(st)
        trim = shapes.arch_ring("arch_trim", S.ARCH_R_R + 0.06, S.ARCH_R_R - 0.008, 0.03, sx * HW, S.YR, S.WHEEL_Z, keep=0.10)
        lib.paint_white(trim)
        out.append(trim)
        liner = shapes.arch_ring("rear_wheel_house", S.ARCH_R_R - 0.006, S.ARCH_R_R - 0.016, HW - S.LOCKER_IN - 0.03,
                                 sx * (HW + S.LOCKER_IN) / 2, S.YR, S.WHEEL_Z, keep=0.05)
        lib.black_plastic(liner)
        out.append(liner)
    return out


def shutter_closed(sx: float, y0: float, y1: float, zb: float, tag: str):
    """Рольставня закрыта: рифлёное полотно, нижняя планка с ручкой-скобой, направляющие по бокам."""
    x_face = sx * (HW - FACE_IN)
    ya, yb = y0 + 0.04, y1 - 0.04
    zt = S.SHUTTER_TOP
    panel = shapes.ribbed_panel("shutter_" + tag, x_face, sx, ya, yb, zb + 0.06, zt)
    lib.alu(panel)
    bar = s3d.fillet(s3d.box("shutter_bar", 0.03, yb - ya, 0.06), 0.008, edges="side")
    lib.alu(bar)
    bar = s3d.at(bar, x=sx * (HW - FACE_IN + 0.004), y=(ya + yb) / 2, z=zb)
    handle = s3d.wire("shutter_handle", [(sx * (HW - FACE_IN + 0.018), (ya + yb) / 2 - 0.16, zb + 0.015),
                                         (sx * (HW - FACE_IN + 0.045), (ya + yb) / 2 - 0.14, zb + 0.012),
                                         (sx * (HW - FACE_IN + 0.045), (ya + yb) / 2 + 0.14, zb + 0.012),
                                         (sx * (HW - FACE_IN + 0.018), (ya + yb) / 2 + 0.16, zb + 0.015)], 0.016,
                     fillet=0.012)
    lib.chrome(handle)
    return [panel, bar, handle] + latches(sx, ya, yb, zb + 0.03)


def shutter_open(sx: float, y0: float, y1: float, zb: float, tag: str):
    """Рольставня поднята: полотно свёрнуто в барабан за верхней полосой, видна нижняя планка и две ламели."""
    ya, yb = y0 + 0.04, y1 - 0.04
    zt = S.SHUTTER_TOP
    panel = shapes.ribbed_panel("shutter_open_" + tag, sx * (HW - FACE_IN), sx, ya, yb, zt - 0.07, zt)
    lib.alu(panel)
    bar = s3d.fillet(s3d.box("shutter_bar", 0.03, yb - ya, 0.06), 0.008, edges="side")
    lib.alu(bar)
    bar = s3d.at(bar, x=sx * (HW - FACE_IN + 0.004), y=(ya + yb) / 2, z=zt - 0.13)
    strap = s3d.box("pull_strap", 0.004, 0.04, 0.30)
    lib.black_plastic(strap)
    strap = s3d.at(strap, x=sx * (HW - FACE_IN + 0.02), y=(ya + yb) / 2, z=zt - 0.43)
    return [panel, bar, strap] + latches(sx, ya, yb, zt - 0.10)


def latches(sx: float, ya: float, yb: float, z_bar: float):
    """Две чёрные защёлки на нижней планке шторки (у краёв) и личинка замка посередине."""
    out = []
    for yy in (ya + 0.10, yb - 0.10):
        lt = s3d.fillet(s3d.box("shutter_latch", 0.028, 0.045, 0.032), 0.006, edges="side")
        lib.black_plastic(lt)
        out.append(s3d.at(lt, x=sx * (HW - FACE_IN + 0.02), y=yy, z=z_bar - 0.012))
    lock = s3d.cylinder("shutter_lock", 0.022, 0.012)
    lib.chrome(lock)
    out.append(s3d.at(lock, x=sx * (HW - FACE_IN + 0.019), y=(ya + yb) / 2 + 0.22, z=z_bar + 0.03, ry=90 * sx))
    return out


def guides(sx: float, y0: float, y1: float, zb: float):
    """Боковые направляющие рольставни (алюминиевый профиль) и козырёк короба барабана — в обоих состояниях."""
    out = []
    hood = s3d.fillet(s3d.box("shutter_hood", 0.022, (y1 - y0) - 0.04, 0.05), 0.008, edges="side")
    lib.alu(hood)
    out.append(s3d.at(hood, x=sx * (HW + 0.002), y=(y0 + y1) / 2, z=S.SHUTTER_TOP - 0.005))
    for yy in (y0 + 0.02, y1 - 0.02):
        g = s3d.box("shutter_guide", 0.02, 0.04, S.SHUTTER_TOP - zb)
        lib.alu(g)
        out.append(s3d.at(g, x=sx * (HW - 0.008), y=yy, z=zb))
    return out


def locker_inside(sx: float, y0: float, y1: float, zb: float, tag: str, dep: float):
    """Отсек изнутри (только в открытом варианте): алюминиевая облицовка, две полки с бортиками,
    светодиодные планки по бокам. Пусто — место под лут."""
    ya, yb = y0 + 0.045, y1 - 0.045
    depth = dep - 0.03            # задняя стенка облицовки на 1 см перед стенкой ниши (ниша — dep от борта)
    h = S.SHUTTER_TOP - zb - 0.005
    liner = s3d.box("locker_liner_" + tag, depth, yb - ya, h)
    s3d.shell(liner, 0.004, open="+X" if sx > 0 else "-X")
    liner = s3d.at(liner, x=sx * (HW - FACE_IN - depth / 2 - 0.008), y=(ya + yb) / 2, z=zb + 0.003)
    lib.alu(liner)
    out = [liner]
    n_shelves = 2 if h > 1.3 else 1
    for k in range(n_shelves):
        z = zb + h * (k + 1) / (n_shelves + 1)
        shelf = s3d.box("shelf", depth - 0.06, yb - ya - 0.02, 0.012)
        lip = s3d.box("shelf_lip", 0.012, yb - ya - 0.02, 0.05)
        shelf = s3d.at(shelf, x=sx * (HW - FACE_IN - depth / 2 - 0.02), y=(ya + yb) / 2, z=z)
        lip = s3d.at(lip, x=sx * (HW - FACE_IN - 0.06), y=(ya + yb) / 2, z=z)
        s3d.join(shelf, lip)
        lib.alu(shelf)
        out.append(shelf)
    for yy in (ya + 0.012, yb - 0.012):
        led = s3d.box("led_strip", 0.012, 0.01, h - 0.10)
        lib.lens(led, "#f7f7ff")
        out.append(s3d.at(led, x=sx * (HW - FACE_IN - 0.035), y=yy, z=zb + 0.05))
    return out


def crew_cut(hull_ob):
    """Под дверями отсека экипажа (полость, проёмы и двери — crew.py): ниша ступеньки с площадкой, поручень."""
    d = S.CREW_DOOR
    out = []
    crew_mod.cut_cavity(hull_ob)
    for sx in (1, -1):
        fr = lib.side(sx * HW, sx)
        # ниша ступеньки под дверью и площадка в ней
        ya2, yb2 = sorted((sx * (d["y0"] + 0.05), sx * (d["y1"] - 0.05)))
        s3d.pocket(hull_ob, shapes.outline(shapes.box_pts(ya2, yb2, 0.60, 0.86), 0.03), 0.20, on=fr)
        step = s3d.fillet(s3d.box("crew_step", 0.20, d["y1"] - d["y0"] - 0.12, 0.03), 0.008, edges="side")
        lib.alu(step)
        out.append(s3d.at(step, x=sx * (HW - 0.10), y=(d["y0"] + d["y1"]) / 2, z=0.60))
        grab = s3d.wire("crew_grab", [(sx * (HW + 0.004), d["y1"] + 0.06, 1.25), (sx * (HW + 0.045), d["y1"] + 0.06, 1.30),
                                      (sx * (HW + 0.045), d["y1"] + 0.06, 2.20), (sx * (HW + 0.004), d["y1"] + 0.06, 2.25)],
                        0.03, fillet=0.03)
        lib.chrome(grab)
        out.append(grab)
    return out


LOWER_DOORS = [(0.12, 1.30), (2.86, 3.46)]       # нижние откидные отсеки под шторками C и A, по Y


def lower_doors(hull_ob):
    """Нижние откидные двери отсеков: швы по контуру в красной юбке, утопленные ручки-лопатки, петли сверху."""
    tools, out = [], []
    z0, z1 = S.LOCKER_BOTTOM + 0.05, S.RUB[0] - 0.03
    for sx in (1, -1):
        fr = lib.side(sx * HW, sx)
        for y0, y1 in LOWER_DOORS:
            ya, yb = sorted((sx * y0, sx * y1))
            tools.append(shapes.ring_tool("lower_seam", shapes.box_pts(ya, yb, z0, z1), 0.03, 0.006, 0.012, fr))
    s3d.cut(hull_ob, tools)
    for sx in (1, -1):
        fr = lib.side(sx * HW, sx)
        for y0, y1 in LOWER_DOORS:
            yc = (y0 + y1) / 2
            ya, yb = sorted((sx * (yc - 0.09), sx * (yc + 0.09)))
            s3d.pocket(hull_ob, shapes.outline(shapes.box_pts(ya, yb, z0 + 0.06, z0 + 0.13), 0.02), 0.025, on=fr)
            paddle = s3d.fillet(s3d.box("paddle_handle", 0.012, 0.15, 0.045), 0.01, edges="side")
            lib.black_plastic(paddle)
            out.append(s3d.at(paddle, x=sx * (HW - 0.018), y=yc, z=z0 + 0.072))
            for yh in (y0 + 0.12, y1 - 0.12):
                hinge = s3d.cylinder("flap_hinge", 0.022, 0.09)
                lib.alu(hinge)
                out.append(s3d.at(hinge, x=sx * (HW + 0.006), y=yh - 0.045, z=z1 - 0.012, rx=-90))
    return out


def intake_boxes():
    """Белые рифлёные короба за кабиной (воздухозаборник и кожух стыка) по обоим бортам."""
    i = S.INTAKE
    out = []
    for sx in (-1, 1):
        x_face = sx * (HW - 0.005)
        # полосы горизонтальные, лицо смотрит по ±X: рифлёная панель вдоль Y
        panel = shapes.ribbed_panel("intake", x_face, sx, i["y0"] + 0.01, i["y1"] - 0.01, i["z0"], i["z1"],
                                    pitch=0.045, groove=0.008, thick=i["t"])
        lib.paint_white(panel)
        out.append(panel)
        cap = s3d.fillet(s3d.box("intake_cap", i["t"] + 0.01, i["y1"] - i["y0"], 0.05), 0.02, edges="top")
        lib.paint_white(cap)
        out.append(s3d.at(cap, x=sx * (HW - i["t"] / 2), y=(i["y0"] + i["y1"]) / 2, z=i["z1"]))
        # круглый оголовок воздухозаборника вверху короба: белый стакан и чёрная решётка с прорезями
        yc = (i["y0"] + i["y1"]) / 2
        head = s3d.fillet(s3d.cylinder("intake_head", 0.26, 0.07), 0.02, edges="top")
        lib.paint_white(head)
        out.append(s3d.at(head, x=sx * (HW - 0.01), y=yc, z=2.60, ry=90 * sx))
        grill = s3d.cylinder("intake_grille", 0.19, 0.02)
        slots = [s3d.at(s3d.box("intake_slot", 0.15, 0.012, 0.05), y=dy, z=-0.01) for dy in (-0.06, -0.03, 0.0, 0.03, 0.06)]
        s3d.cut(grill, slots)
        lib.black_plastic(grill)
        out.append(s3d.at(grill, x=sx * (HW + 0.05), y=yc, z=2.60, ry=90 * sx))
        vent = s3d.fillet(s3d.box("crew_vent", 0.012, 0.075, 0.14), 0.01, edges="side")
        cuts = [s3d.at(s3d.box("vent_slot", 0.03, 0.05, 0.008), z=0.02 + 0.022 * k) for k in range(5)]
        s3d.cut(vent, cuts)
        lib.black_plastic(vent)
        out.append(s3d.at(vent, x=sx * (HW + 0.004), y=S.BODY_FRONT + 0.06, z=2.50))
    # перемычка между кабиной и кузовом над рамой — тёмная, закрывает просвет
    gap = s3d.box("cab_gap_cover", S.BODY_W - 2 * i["t"], i["y1"] - i["y0"] - 0.02, i["z1"] - 1.2)
    lib.steel_dark(gap)
    out.append(s3d.at(gap, y=(i["y0"] + i["y1"]) / 2, z=1.2))
    return out


def rear():
    """Задняя часть: угловые стойки с фонарями и маячками, рольставня насосного отсека, панель насоса
    с патрубками, подножка, лестница на крышу справа."""
    out = []
    yb = S.BODY_BACK
    for sx in (-1, 1):
        col = s3d.fillet(s3d.box("rear_column", S.REAR_COL, 0.34, S.BAND[1] - S.LOCKER_BOTTOM), 0.03, edges="side")
        lib.paint_red(col)
        out.append(s3d.at(col, x=sx * (HW - S.REAR_COL / 2 + 0.005), y=yb - 0.15, z=S.LOCKER_BOTTOM))
        xc = sx * (HW - S.REAR_COL / 2 + 0.005)
        for z, color in ((0.62, "#c81010"), (0.76, "#f0a020"), (0.90, "#f4f4f4"), (1.60, "#c81010"),
                         (1.74, "#c81010")):
            lamp = s3d.cylinder("rear_lamp", 0.11, 0.025)
            lib.lens(lamp, color)
            out.append(s3d.at(lamp, x=xc, y=yb + 0.02, z=z, rx=-90))
            rim_ = s3d.tube("lamp_rim", 0.13, 0.105, 0.03)
            lib.chrome(rim_)
            out.append(s3d.at(rim_, x=xc, y=yb + 0.015, z=z, rx=-90))
            cup = s3d.shell(s3d.dome("lamp_reflector", 0.10, 0.035), 0.002, open="bottom")
            lib.chrome(cup)
            out.append(s3d.at(cup, x=xc, y=yb + 0.016, z=z, rx=90))
            bulb = s3d.sphere("lamp_bulb", 0.025)
            s3d.material(bulb, "glass", color="#f5f0e0", opacity=0.6)
            out.append(s3d.at(bulb, x=xc, y=yb + 0.0, z=z - 0.0125))
        beacon = s3d.fillet(s3d.box("rear_beacon", 0.20, 0.20, 0.16), 0.06, edges="side")
        s3d.fillet(beacon, 0.04, edges="top")
        lib.lens(beacon, "#2050d8")
        out.append(s3d.at(beacon, x=xc, y=yb - 0.12, z=S.BAND[1]))
    cam = s3d.fillet(s3d.box("rear_camera", 0.10, 0.06, 0.08), 0.015, edges="side")
    lib.black_plastic(cam)
    out.append(s3d.at(cam, y=yb + 0.03, z=S.BAND[0] + 0.06))
    # насос под кузовом между нижними отсеками: улитка, всасывающий патрубок к задней муфте, коллектор к напорным
    volute = s3d.fillet(s3d.cylinder("pump_volute", 0.42, 0.24), 0.04, edges="top bottom")
    lib.steel_dark(volute)
    out.append(s3d.at(volute, y=yb - 0.62, z=0.80, rx=-90))
    hub_ = s3d.cylinder("pump_drive", 0.20, 0.30)
    lib.steel_dark(hub_)
    out.append(s3d.at(hub_, y=yb - 0.92, z=0.80, rx=-90))
    suction = s3d.cylinder("pump_suction_pipe", 0.15, 0.36)
    lib.steel_dark(suction)
    out.append(s3d.at(suction, y=yb - 0.38, z=0.80, rx=-90))
    manifold = lib.along_x(s3d.cylinder("pump_manifold", 0.085, 0.80), -0.40, yb - 0.16, 0.66)
    lib.steel_dark(manifold)
    out.append(manifold)
    for x in (-0.38, 0.38):
        riser = s3d.wire("outlet_pipe", [(x, yb - 0.16, 0.66), (x, yb - 0.16, 0.74), (x, yb - 0.02, 0.74)], 0.085, fillet=0.06)
        lib.steel_dark(riser)
        pipe = s3d.cylinder("outlet", 0.11, 0.10)
        cap = s3d.cylinder("outlet_cap", 0.13, 0.04)
        lib.alu(pipe)
        lib.alu(cap)
        chain = s3d.wire("cap_chain", [(x + 0.06, yb + 0.10, 0.74), (x + 0.10, yb + 0.06, 0.62), (x + 0.05, yb + 0.0, 0.58)], 0.006)
        lib.steel_dark(chain)
        out += [riser, s3d.at(pipe, x=x, y=yb - 0.02, z=0.74, rx=-90), s3d.at(cap, x=x, y=yb + 0.08, z=0.74, rx=-90), chain]
    guard = s3d.box("pump_guard", 1.10, 0.04, 0.05)
    lib.steel_dark(guard)
    out.append(s3d.at(guard, y=yb - 0.05, z=S.LOCKER_BOTTOM))
    st = S.REAR_STEP
    depth = st["y1"] - yb + 0.05
    step = s3d.fillet(s3d.box("rear_step", st["w"], depth, st["z1"] - st["z0"]), 0.015, edges="side")
    s3d.at(step, y=(yb - 0.05 + st["y1"]) / 2, z=st["z0"])
    top = s3d.Frame((0, (yb - 0.05 + st["y1"]) / 2, st["z1"]))
    s3d.hole(step, 0.022, on=s3d.grid(34, 4, 0.062, 0.058, stagger=True, on=top))
    lib.alu(step)
    out.append(step)
    # ремни крепления рукавов: с кромки крыши вниз по рольставне (ткань)
    for x in (0.48, -0.30):
        strap = s3d.wire("hose_strap_hang", [(x, yb - 0.06, S.BAND[1] + 0.10), (x, yb + 0.03, S.BAND[1] - 0.02),
                                             (x + 0.02, yb + 0.035, 1.60), (x + 0.03, yb + 0.03, 1.18)], 0.012, fillet=0.05)
        s3d.material(strap, "fabric", color="#5f7d55")
        out.append(strap)
    # лестница на крышу у правой (−X) стойки
    xl = -(HW - S.REAR_COL / 2 + 0.005)
    rails = []
    for dx in (-0.17, 0.17):
        rails.append(s3d.wire("ladder_rail", [(xl + dx, yb + 0.06, 0.58), (xl + dx, yb + 0.06, S.BAND[1] + 0.30),
                                              (xl + dx, yb - 0.10, S.BAND[1] + 0.45)], 0.032, fillet=0.08))
    rungs = [s3d.extrude("ladder_rung", s3d.rect(0.03, 0.025, r=0.006), 0.34, both=True,
                         on=lib.side(xl, 1, yb + 0.06, 0.70 + 0.28 * k)) for k in range(9)]
    for r in rails + rungs:
        lib.alu(r)
    out += rails + rungs
    return out


def side_details():
    """Боковые габаритные огни по низу, противооткатные упоры в держателях справа, номер и его фонарь
    на левой задней стойке, катафоты, всасывающий патрубок с крышкой, вентили, буксирная петля."""
    out = []
    for sx in (-1, 1):
        for y in (0.20, 1.20, 3.35):
            lamp = s3d.fillet(s3d.box("side_marker", 0.02, 0.10, 0.045), 0.012, edges="side")
            lib.lens(lamp, "#f0a020")
            out.append(s3d.at(lamp, x=sx * (HW + 0.008), y=y, z=0.62))
    for y in (S.YR + S.ARCH_R_R + 0.20, S.YR + S.ARCH_R_R + 0.48):
        hold = s3d.box("chock_holder", 0.06, 0.24, 0.16)
        lib.steel_dark(hold)
        out.append(s3d.at(hold, x=-(S.LOCKER_IN + 0.03), y=y, z=S.LOCKER_BOTTOM - 0.15))
        chock = s3d.wedge("wheel_chock", 0.14, 0.24, 0.14, top=0.06)
        s3d.material(chock, "plastic", color="#e2b21a")
        out.append(s3d.at(chock, x=-(S.LOCKER_IN + 0.12), y=y, z=S.LOCKER_BOTTOM - 0.14))
    yb = S.BODY_BACK
    xl = HW - S.REAR_COL / 2 + 0.005
    plate = s3d.box("plate_rear", 0.26, 0.006, 0.17)
    s3d.material(plate, "painted_metal", color="#f0f0ea")
    out.append(s3d.at(plate, x=xl, y=yb + 0.025, z=1.10))
    plamp = s3d.fillet(s3d.box("plate_lamp", 0.10, 0.04, 0.03), 0.01, edges="side")
    lib.black_plastic(plamp)
    out.append(s3d.at(plamp, x=xl, y=yb + 0.04, z=1.28))
    for sx in (-1, 1):
        refl = s3d.box("rear_reflector", 0.16, 0.006, 0.05)
        lib.lens(refl, "#b00000")
        out.append(s3d.at(refl, x=sx * xl, y=yb + 0.025, z=0.53))
    inlet = s3d.cylinder("suction_inlet", 0.16, 0.10)
    cap = s3d.cylinder("suction_cap", 0.19, 0.05)
    lugs = s3d.at(s3d.box("cap_lug", 0.05, 0.03, 0.05), on=s3d.ring(2, 0.11))
    s3d.join(cap, lugs)
    lib.alu(inlet)
    lib.alu(cap)
    out += [s3d.at(inlet, y=yb - 0.03, z=0.80, rx=-90), s3d.at(cap, y=yb + 0.07, z=0.80, rx=-90)]
    for x in (-0.62, 0.62):
        valve = s3d.wire("valve_handle", [(x, yb + 0.02, 0.62), (x, yb + 0.10, 0.62), (x + 0.10, yb + 0.12, 0.62)], 0.022, fillet=0.03)
        s3d.material(valve, "painted_metal", color="#c8a018")
        out.append(valve)
    hook = s3d.at(s3d.torus("tow_hook_rear", 0.12, 0.03), y=S.REAR_STEP["y1"] - 0.02, z=S.REAR_STEP["z0"] - 0.06, rx=90)
    lib.steel_dark(hook)
    out.append(hook)
    return out


def rear_shutter_closed() -> list:
    """Рольставня насосного отсека закрыта: окрашенное полотно, нижняя планка с двумя ручками, окно приборов насоса."""
    out = []
    yb = S.BODY_BACK
    rs = S.REAR_SHUTTER
    sh = shapes.ribbed_panel_x("rear_shutter", yb - 0.012, 1.0, -rs["x"] + 0.04, rs["x"] - 0.04, rs["z0"] + 0.06, rs["z1"])
    lib.paint_red(sh)
    bar = s3d.fillet(s3d.box("rear_shutter_bar", 2 * rs["x"] - 0.08, 0.03, 0.06), 0.008, edges="side")
    lib.alu(bar)
    out += [sh, s3d.at(bar, y=yb - 0.008, z=rs["z0"])]
    bezel = s3d.fillet(s3d.box("gauge_bezel", 0.38, 0.03, 0.16), 0.03, edges="side")
    lib.black_plastic(bezel)
    out.append(s3d.at(bezel, y=yb - 0.0, z=1.80))
    for x in (-0.085, 0.085):
        dial = s3d.cylinder("gauge_dial", 0.10, 0.008)
        s3d.material(dial, "plastic", color="#e8e8e2")
        ring = s3d.tube("gauge_ring", 0.115, 0.098, 0.014)
        lib.chrome(ring)
        out += [s3d.at(dial, x=x, y=yb + 0.015, z=1.88, rx=-90), s3d.at(ring, x=x, y=yb + 0.012, z=1.88, rx=-90)]
    gauges = s3d.box("gauge_window", 0.34, 0.006, 0.12)
    lib.glass(gauges)
    out.append(s3d.at(gauges, y=yb + 0.024, z=1.82))
    for x in (-0.45, 0.45):
        hd = s3d.wire("rear_shutter_handle", [(x - 0.07, yb + 0.002, rs["z0"] + 0.02), (x - 0.06, yb + 0.04, rs["z0"] + 0.015),
                                              (x + 0.06, yb + 0.04, rs["z0"] + 0.015), (x + 0.07, yb + 0.002, rs["z0"] + 0.02)],
                      0.016, fillet=0.012)
        lib.black_plastic(hd)
        out.append(hd)
    return out


def rear_compartment_open() -> list:
    """Насосный отсек открыт: полотно свёрнуто наверху, облицовка, панель управления насосом (манометр и мановакуумметр,
    тахометр, клавиши, рукоятка газа), рычаги задвижек, сливные краны, катушка с рукавом наверху, светодиодные планки."""
    out = []
    yb = S.BODY_BACK
    rs = S.REAR_SHUTTER
    zt = rs["z1"]
    sh = shapes.ribbed_panel_x("rear_shutter_open", yb - 0.012, 1.0, -rs["x"] + 0.04, rs["x"] - 0.04, zt - 0.07, zt)
    lib.paint_red(sh)
    bar = s3d.fillet(s3d.box("rear_shutter_bar", 2 * rs["x"] - 0.08, 0.03, 0.06), 0.008, edges="side")
    lib.alu(bar)
    out += [sh, s3d.at(bar, y=yb - 0.008, z=zt - 0.13)]
    w = 2 * rs["x"] - 0.10
    dep = 0.52
    liner = s3d.box("pump_bay_liner", w, dep, zt - rs["z0"] - 0.006)
    s3d.shell(liner, 0.004, open="+Y")
    liner = s3d.at(liner, y=yb - 0.02 - dep / 2, z=rs["z0"] + 0.003)
    lib.alu(liner)
    out.append(liner)
    yp = yb - 0.02 - dep + 0.006
    panel = s3d.fillet(s3d.box("pump_panel", w - 0.06, 0.02, 1.02), 0.01, edges="side")
    s3d.material(panel, "brushed_steel", color="#9a9da0")
    out.append(s3d.at(panel, y=yp + 0.01, z=rs["z0"] + 0.08))
    yf = yp + 0.021
    for x, z, d in ((-0.24, 1.78, 0.17), (0.0, 1.78, 0.17), (0.24, 1.80, 0.12), (-0.52, 1.82, 0.09), (0.52, 1.82, 0.09)):
        dial = s3d.cylinder("pump_gauge", d, 0.01)
        s3d.material(dial, "plastic", color="#f1f1ec")
        ring = s3d.tube("pump_gauge_ring", d + 0.016, d, 0.02)
        lib.chrome(ring)
        needle = s3d.box("pump_gauge_needle", d * 0.4, 0.003, 0.005)
        s3d.material(needle, "plastic", color="#c01010")
        out += [s3d.at(dial, x=x, y=yf, z=z, rx=-90), s3d.at(ring, x=x, y=yf - 0.004, z=z, rx=-90),
                s3d.at(needle, x=x + d * 0.1, y=yf + 0.012, z=z, ry=-40)]
    box = s3d.fillet(s3d.box("pump_control_box", 0.36, 0.08, 0.16), 0.015, edges="side")
    lib.black_plastic(box)
    out.append(s3d.at(box, x=0.0, y=yf + 0.04, z=1.50))
    for k in range(6):
        btn = s3d.cylinder("pump_button", 0.03, 0.012)
        s3d.material(btn, "plastic", color=("#20a040", "#c02020", "#e0a020")[k % 3])
        out.append(s3d.at(btn, x=-0.13 + 0.052 * k, y=yf + 0.08, z=1.58, rx=-90))
    knob = s3d.cylinder("throttle_knob", 0.06, 0.04)
    s3d.material(knob, "plastic", color="#101010")
    out.append(s3d.at(knob, x=0.32, y=yf, z=1.52, rx=-90))
    for x, color in ((-0.42, "#e0b020"), (-0.14, "#e0b020"), (0.14, "#2050d0"), (0.42, "#e0b020")):
        pivot = s3d.cylinder("valve_pivot", 0.05, 0.05)
        lib.steel_dark(pivot)
        lever = s3d.wire("valve_lever", [(x, yf + 0.05, 1.24), (x + 0.02, yf + 0.10, 1.42)], 0.024)
        s3d.material(lever, "painted_metal", color=color, roughness=0.4)
        grip = s3d.at(s3d.sphere("valve_grip", 0.045), x=x + 0.02, y=yf + 0.10, z=1.40)
        s3d.material(grip, "plastic", color="#111111")
        out += [s3d.at(pivot, x=x, y=yf, z=1.24, rx=-90), lever, grip]
    for x in (-0.30, 0.30):
        drain = s3d.wire("drain_valve", [(x, yf, 1.10), (x, yf + 0.08, 1.10), (x, yf + 0.08, 1.06)], 0.03, fillet=0.02)
        lib.chrome(drain)
        out.append(drain)
    # катушка с рукавом наверху: барабан, щёки, витки рукава, ось на кронштейнах
    yr = yb - 0.30
    zr = zt - 0.30
    drum = lib.along_x(s3d.cylinder("hose_reel_drum", 0.26, w - 0.30), -(w - 0.30) / 2, yr, zr)
    lib.steel_dark(drum)
    out.append(drum)
    for x in (-(w - 0.30) / 2, (w - 0.30) / 2 - 0.012):
        cheek = lib.along_x(s3d.cylinder("hose_reel_cheek", 0.46, 0.012), x, yr, zr)
        s3d.material(cheek, "painted_metal", color="#b01418", roughness=0.4)
        out.append(cheek)
    n_turns = int((w - 0.34) / 0.052)
    for k in range(n_turns):
        x = -(w - 0.34) / 2 + 0.026 + k * 0.052
        coil = s3d.at(s3d.torus("hose_coil", 0.36, 0.05), x=x, y=yr, z=zr, ry=90)
        s3d.material(coil, "rubber", color="#7a1d1a")
        out.append(coil)
    nozzle = s3d.wire("hose_reel_end", [(w / 2 - 0.20, yr + 0.18, zr - 0.10), (w / 2 - 0.20, yr + 0.22, zr - 0.40)], 0.05)
    s3d.material(nozzle, "rubber", color="#7a1d1a")
    gun = s3d.cone("hose_reel_nozzle", 0.06, 0.18, d2=0.035)
    lib.alu(gun)
    out += [nozzle, s3d.at(gun, x=w / 2 - 0.20, y=yr + 0.22, z=zr - 0.58)]
    for x in (-w / 2 + 0.02, w / 2 - 0.02):
        led = s3d.box("pump_bay_led", 0.01, 0.012, zt - rs["z0"] - 0.20)
        lib.lens(led, "#f7f7ff")
        out.append(s3d.at(led, x=x, y=yb - 0.06, z=rs["z0"] + 0.10))
    return out


def mudflap_brackets() -> list:
    """Планки задних брызговиков: стальная полоса под низом отсека, к ней прикручен верх брызговика."""
    out = []
    for sx in (-1, 1):
        rail = s3d.fillet(s3d.box("mudflap_rail", 0.66, 0.025, 0.03), 0.006, edges="side")
        lib.steel_dark(rail)
        out.append(s3d.at(rail, x=sx * (S.TRACK_R / 2), y=S.YR + 0.80, z=S.LOCKER_BOTTOM - 0.03))
        for dx in (-0.25, 0.0, 0.25):
            bolt = s3d.extrude("mudflap_bolt", s3d.polygon(6, 0.02), 0.008, on=lib.rear(S.YR + 0.8125, x=sx * (S.TRACK_R / 2) + dx,
                                                                                         z=S.LOCKER_BOTTOM - 0.015))
            lib.steel_dark(bolt)
            out.append(bolt)
    return out


def build() -> dict:
    h = hull()
    crew = crew_cut(h) + lower_doors(h)
    s3d.fillet(h, 0.012, edges="side")          # после вырезов: скругление до них ломает EXACT на борту −X
    common = [h] + crew + band() + rub_strips() + intake_boxes() + rear() + side_details() + crew_mod.hinge_body_parts() \
        + crew_mod.interior() + mudflap_brackets()
    closed, opened = rear_shutter_closed(), rear_compartment_open()
    for side, sx in (("L", 1.0), ("R", -1.0)):
        d = crew_mod.door(sx)
        d_open = shapes.copy_tree(d)
        piv = (sx * (HW + 0.010), crew_mod.PIVOT_Y)
        closed.append(shapes.hinged(f"Hinge_CrewDoor_{side}_closed", d, piv, 0.0))
        opened.append(shapes.hinged(f"Hinge_CrewDoor_{side}_open", d_open, piv, -sx * crew_mod.DOOR_OPEN_DEG))
    for sx in (-1, 1):
        for k, (y0, y1, zb) in enumerate(S.SHUTTERS):
            tag = f"{'L' if sx > 0 else 'R'}{k + 1}"
            common += guides(sx, y0, y1, zb)
            closed += shutter_closed(sx, y0, y1, zb, tag)
            opened += shutter_open(sx, y0, y1, zb, tag) + locker_inside(sx, y0, y1, zb, tag, locker_depth(k))
    return {"common": [s3d.group("Кузов", *common)],
            "closed": [s3d.group("Рольставни и двери закрыты", *closed)],
            "open": [s3d.group("Рольставни подняты, двери открыты", *opened)]}
