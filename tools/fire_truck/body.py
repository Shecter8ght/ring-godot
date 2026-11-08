"""Надстройка: отсек экипажа с дверью, боковые отсеки под рольставнями (закрыты / подняты, внутри полки),
нижние отсеки снаружи рамы с задней аркой, полосы, задний насосный отсек, угловые стойки с фонарями,
подножка, лестница на крышу, белые рифлёные короба за кабиной."""
from __future__ import annotations

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
            st = s3d.fillet(s3d.box("rub_strip", 0.025, y1 - y0, zt - zb), 0.008, edges="side")
            lib.paint_white(st)
            out.append(s3d.at(st, x=sx * (HW + 0.0125), y=(y0 + y1) / 2, z=zb))
        trim = s3d.at(s3d.tube("arch_trim", 2 * (S.ARCH_R_R + 0.06), 2 * (S.ARCH_R_R - 0.008), 0.03), z=-0.015)
        s3d.cut(trim, s3d.at(s3d.box("trim_cut", 2.0, 2 * S.ARCH_R_R + 0.4, 0.2), x=1.0 + 0.10, z=-0.1))
        trim = s3d.at(trim, x=sx * (HW + 0.0), y=S.YR, z=S.WHEEL_Z, ry=90)
        lib.paint_white(trim)
        out.append(trim)
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
    return [panel, bar, handle]


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
    return [panel, bar, strap]


def guides(sx: float, y0: float, y1: float, zb: float):
    """Боковые направляющие рольставни (алюминиевый профиль) — видны в обоих состояниях."""
    out = []
    for yy in (y0 + 0.02, y1 - 0.02):
        g = s3d.box("shutter_guide", 0.02, 0.04, S.SHUTTER_TOP - zb)
        lib.alu(g)
        out.append(s3d.at(g, x=sx * (HW - 0.008), y=yy, z=zb))
    return out


def locker_inside(sx: float, y0: float, y1: float, zb: float, tag: str, dep: float):
    """Отсек изнутри (только в открытом варианте): алюминиевая облицовка, две полки с бортиками,
    светодиодные планки по бокам. Пусто — место под лут."""
    ya, yb = y0 + 0.045, y1 - 0.045
    depth = dep + 0.02
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
    """Шов двери и проём окна отсека экипажа в корпусе (обе стороны), стёкла и ручки."""
    d, w = S.CREW_DOOR, S.CREW_WIN
    tools, out = [], []
    for sx in (1, -1):
        fr = lib.side(sx * HW, sx)
        ya, yb = sorted((sx * d["y0"], sx * d["y1"]))
        tools.append(shapes.ring_tool("crew_seam", shapes.box_pts(ya, yb, d["z0"], d["z1"]), 0.04, 0.006, 0.012, fr))
    s3d.cut(hull_ob, tools)
    for sx in (1, -1):
        fr = lib.side(sx * HW, sx)
        ya, yb = sorted((sx * w["y0"], sx * w["y1"]))
        rect = shapes.box_pts(ya, yb, w["z0"], w["z1"])
        s3d.pocket(hull_ob, shapes.outline(rect, 0.04), 0.03, on=fr)
        out.append(shapes.seal_ring("crew_seal", rect, 0.04, 0.018, 0.01, fr.offset(-0.03)))
        g = s3d.extrude("crew_glass", shapes.outline(rect, 0.03), 0.006, on=fr.offset(-0.022))
        lib.glass(g)
        out.append(g)
        h = s3d.fillet(s3d.box("crew_handle", 0.03, 0.20, 0.05), 0.015, edges="side")
        lib.black_plastic(h)
        out.append(s3d.at(h, x=sx * (HW + 0.006), y=d["y0"] + 0.20 if sx > 0 else d["y0"] + 0.20, z=1.72))
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
        beacon = s3d.fillet(s3d.box("rear_beacon", 0.20, 0.20, 0.16), 0.06, edges="side")
        s3d.fillet(beacon, 0.04, edges="top")
        lib.lens(beacon, "#2050d8")
        out.append(s3d.at(beacon, x=xc, y=yb - 0.12, z=S.BAND[1]))
    rs = S.REAR_SHUTTER
    sh = shapes.ribbed_panel_x("rear_shutter", yb - 0.012, 1.0, -rs["x"] + 0.04, rs["x"] - 0.04, rs["z0"] + 0.06, rs["z1"])
    lib.paint_red(sh)
    bar = s3d.fillet(s3d.box("rear_shutter_bar", 2 * rs["x"] - 0.08, 0.03, 0.06), 0.008, edges="side")
    lib.alu(bar)
    out += [sh, s3d.at(bar, y=yb - 0.008, z=rs["z0"])]
    gauges = s3d.fillet(s3d.box("gauge_window", 0.34, 0.02, 0.12), 0.02, edges="side")
    lib.glass(gauges)
    out.append(s3d.at(gauges, y=yb - 0.0, z=1.85))
    # панель насоса внизу: патрубки с заглушками
    panel = s3d.box("pump_panel", 2 * (HW - S.REAR_COL), 0.08, S.BODY_FLOOR + 0.02 - S.LOCKER_BOTTOM)
    lib.steel_dark(panel)
    out.append(s3d.at(panel, y=yb - 0.06, z=S.LOCKER_BOTTOM))
    for x in (-0.38, 0.38):
        pipe = s3d.cylinder("outlet", 0.11, 0.12)
        cap = s3d.cylinder("outlet_cap", 0.13, 0.04)
        lib.alu(pipe)
        lib.alu(cap)
        out += [s3d.at(pipe, x=x, y=yb - 0.03, z=0.74, rx=-90), s3d.at(cap, x=x, y=yb + 0.09, z=0.74, rx=-90)]
    st = S.REAR_STEP
    step = s3d.fillet(s3d.box("rear_step", st["w"], st["y1"] - yb + 0.05, st["z1"] - st["z0"]), 0.015, edges="side")
    lib.alu(step)
    out.append(s3d.at(step, y=(yb - 0.05 + st["y1"]) / 2, z=st["z0"]))
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


def build() -> dict:
    h = hull()
    crew = crew_cut(h)
    s3d.fillet(h, 0.012, edges="side")          # после вырезов: скругление до них ломает EXACT на борту −X
    common = [h] + crew + band() + rub_strips() + intake_boxes() + rear() + side_details()
    closed, opened = [], []
    for sx in (-1, 1):
        for k, (y0, y1, zb) in enumerate(S.SHUTTERS):
            tag = f"{'L' if sx > 0 else 'R'}{k + 1}"
            common += guides(sx, y0, y1, zb)
            closed += shutter_closed(sx, y0, y1, zb, tag)
            opened += shutter_open(sx, y0, y1, zb, tag) + locker_inside(sx, y0, y1, zb, tag, locker_depth(k))
    return {"common": [s3d.group("Кузов", *common)],
            "closed": [s3d.group("Рольставни закрыты", *closed)],
            "open": [s3d.group("Рольставни подняты, отсеки", *opened)]}
