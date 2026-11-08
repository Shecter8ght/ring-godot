"""Отсек экипажа: полость в кузове, проёмы дверей, двери на петлях (толщина, окно, уплотнитель, ручки, обивка),
сиденья с дыхательными аппаратами в спинках, обшивка, пол, плафоны, поручень, рации.

Метры, оси машины. Отсек — по Y от BODY_FRONT до CREW["y1"], во всю ширину кузова; двери — S.CREW_DOOR.
"""
from __future__ import annotations

import lib
import shapes
import spec as S
from lib import s3d

HW = S.BODY_W / 2
D = S.CREW_DOOR
W = S.CREW_WIN
WALL = 0.045                      # толщина стенки кузова у отсека
CAV = dict(y0=S.BODY_FRONT + WALL, y1=S.CREW["y1"] - 0.04, z0=1.08, z1=2.76)
DOOR_T = 0.05
GAP = 0.005
PIVOT_Y = D["y0"] - 0.005
DOOR_OPEN_DEG = 72.0


def _rect(sx: float, y0: float, y1: float, z0: float, z1: float) -> list:
    """Прямоугольник (Y, Z) в координатах рамки борта: у правого борта ось x рамки идёт по −Y."""
    a, b = sorted((sx * y0, sx * y1))
    return shapes.box_pts(a, b, z0, z1)


def cut_cavity(hull) -> None:
    """Полость отсека и сквозные проёмы дверей (до скругления корпуса)."""
    cav = s3d.box("crew_cavity", 2 * (HW - WALL), CAV["y1"] - CAV["y0"], CAV["z1"] - CAV["z0"])
    tools = [s3d.at(cav, y=(CAV["y0"] + CAV["y1"]) / 2, z=CAV["z0"])]
    for sx in (1, -1):
        tools.append(s3d.extrude("crew_aperture", shapes.outline(_rect(sx, D["y0"], D["y1"], D["z0"], D["z1"]), 0.04),
                                 0.16, both=True, on=lib.side(sx * HW, sx)))
    s3d.cut(hull, tools)


def door(sx: float) -> list:
    """Дверь (сторона sx): створка толщиной 5 см со скруглёнными кромками и окном, стекло посередине толщины,
    уплотнитель снаружи, обивка изнутри, ручки, личинка, половинки петель."""
    out = []
    rect = _rect(sx, D["y0"] + GAP, D["y1"] - GAP, D["z0"] + GAP, D["z1"] - GAP)
    leaf = s3d.extrude("crew_door", shapes.outline(rect, 0.035), DOOR_T, on=lib.side(sx * (HW - DOOR_T), sx))
    win = _rect(sx, W["y0"], W["y1"], W["z0"], W["z1"])
    s3d.cut(leaf, s3d.extrude("crew_win_cut", shapes.outline(win, 0.035), 0.3, both=True, on=lib.side(sx * HW, sx)))
    s3d.fillet(leaf, 0.006, edges="top bottom")
    lib.paint_red(leaf)
    out.append(leaf)
    g = s3d.extrude("crew_glass", shapes.outline(_rect(sx, W["y0"] + 0.002, W["y1"] - 0.002, W["z0"] + 0.002, W["z1"] - 0.002),
                                                 0.033), 0.006, on=lib.side(sx * (HW - DOOR_T / 2 - 0.003), sx))
    lib.glass(g)
    out.append(g)
    out.append(shapes.seal_ring("crew_win_seal", win, 0.035, 0.016, 0.008, lib.side(sx * HW, sx)))
    inner = _rect(sx, D["y0"] + 0.03, D["y1"] - 0.03, D["z0"] + 0.04, D["z1"] - 0.04)
    inner = _rect(-sx, D["y0"] + 0.03, D["y1"] - 0.03, D["z0"] + 0.04, D["z1"] - 0.04)     # рамка смотрит внутрь: ось x — по ∓Y
    card = s3d.extrude("crew_door_card", shapes.outline(inner, 0.03), 0.008, on=lib.side(sx * (HW - DOOR_T), -sx))
    s3d.cut(card, s3d.extrude("crew_card_win", shapes.outline(_rect(sx, W["y0"] - 0.02, W["y1"] + 0.02, W["z0"] - 0.02,
                                                                    W["z1"] + 0.02), 0.045), 0.3, both=True,
                              on=lib.side(sx * HW, sx)))
    s3d.material(card, "plastic", color="#34373a", roughness=0.65)
    out.append(card)
    cup = s3d.fillet(s3d.box("crew_handle_cup", 0.012, 0.24, 0.08), 0.015, edges="side")
    lib.black_plastic(cup)
    hd = s3d.fillet(s3d.box("crew_handle", 0.03, 0.20, 0.045), 0.015, edges="side")
    lib.black_plastic(hd)
    lock = s3d.cylinder("crew_lock", 0.028, 0.012)
    lib.chrome(lock)
    ih = s3d.fillet(s3d.box("crew_inner_handle", 0.03, 0.14, 0.03), 0.01, edges="side")
    lib.chrome(ih)
    arm = s3d.fillet(s3d.box("crew_door_armrest", 0.05, 0.36, 0.05), 0.018, edges="side")
    s3d.material(arm, "plastic", color="#2a2c2f", roughness=0.6)
    out += [s3d.at(cup, x=sx * (HW - 0.002), y=D["y1"] - 0.20, z=1.70),
            s3d.at(hd, x=sx * (HW + 0.008), y=D["y1"] - 0.20, z=1.715),
            s3d.at(lock, x=sx * (HW + 0.004), y=D["y1"] - 0.06, z=1.74, ry=90 * sx),
            s3d.at(ih, x=sx * (HW - DOOR_T - 0.022), y=D["y1"] - 0.20, z=1.80),
            s3d.at(arm, x=sx * (HW - DOOR_T - 0.032), y=(D["y0"] + D["y1"]) / 2, z=1.62)]
    for z in (D["z0"] + 0.30, D["z1"] - 0.30):
        lf = s3d.fillet(s3d.box("crew_hinge_leaf_door", 0.012, 0.06, 0.10), 0.004, edges="side")
        lib.steel_dark(lf)
        out.append(s3d.at(lf, x=sx * (HW + 0.004), y=D["y0"] + 0.035, z=z))
    return out


def hinge_body_parts() -> list:
    out = []
    for sx in (1, -1):
        for z in (D["z0"] + 0.30, D["z1"] - 0.30):
            pin = s3d.cylinder("crew_hinge_pin", 0.022, 0.11)
            lib.steel_dark(pin)
            lf = s3d.fillet(s3d.box("crew_hinge_leaf_body", 0.012, 0.05, 0.10), 0.004, edges="side")
            lib.steel_dark(lf)
            out += [s3d.at(pin, x=sx * (HW + 0.010), y=PIVOT_Y, z=z - 0.005), s3d.at(lf, x=sx * (HW + 0.004), y=PIVOT_Y - 0.028, z=z)]
    return out


def seat(x: float, y_back: float, facing: float) -> list:
    """Сиденье экипажа: каркас, подушка, боковые подушки спинки, между ними — дыхательный аппарат (баллон в ложементе,
    спинка-рама, лямки), подголовник. facing = +1 — лицом назад машины (+Y), −1 — вперёд."""
    out = []
    z0 = CAV["z0"] + 0.012
    yc = y_back + facing * 0.25
    base = s3d.fillet(s3d.box("crew_seat_base", 0.44, 0.38, 0.37), 0.02, edges="side")
    lib.steel_dark(base)
    out.append(s3d.at(base, x=x, y=yc, z=z0))
    cush = s3d.fillet(s3d.box("crew_seat_cushion", 0.50, 0.46, 0.11), 0.05, edges="side")
    s3d.fillet(cush, 0.035, edges="top")
    s3d.material(cush, "fabric", color="#2b2e33")
    out.append(s3d.at(cush, x=x, y=yc, z=z0 + 0.37))
    yb = y_back + facing * 0.06
    for dx in (-0.19, 0.19):
        pad = s3d.fillet(s3d.box("crew_seat_back_pad", 0.12, 0.10, 0.62), 0.04, edges="side")
        s3d.fillet(pad, 0.03, edges="top")
        s3d.material(pad, "fabric", color="#2b2e33")
        out.append(s3d.at(pad, x=x + dx, y=yb, z=z0 + 0.50))
    plate = s3d.fillet(s3d.box("scba_backplate", 0.30, 0.03, 0.56), 0.03, edges="side")
    lib.black_plastic(plate)
    out.append(s3d.at(plate, x=x, y=y_back + facing * 0.03, z=z0 + 0.52))
    cyl = s3d.fillet(s3d.cylinder("scba_cylinder", 0.17, 0.58), 0.06, edges="top bottom")
    s3d.material(cyl, "painted_metal", color="#2d2f31", roughness=0.35)
    band = s3d.tube("scba_band", 0.176, 0.168, 0.05)
    s3d.material(band, "plastic", color="#d8b21c", roughness=0.4)
    valve = s3d.cylinder("scba_valve", 0.05, 0.07)
    lib.chrome(valve)
    yc_cyl = y_back + facing * 0.13
    out += [s3d.at(cyl, x=x, y=yc_cyl, z=z0 + 0.53), s3d.at(band, x=x, y=yc_cyl, z=z0 + 0.86),
            s3d.at(valve, x=x, y=yc_cyl, z=z0 + 1.11)]
    for dx in (-0.09, 0.09):
        strap = s3d.wire("scba_strap", [(x + dx, y_back + facing * 0.05, z0 + 1.08), (x + dx * 1.3, y_back + facing * 0.24, z0 + 0.98),
                                        (x + dx * 1.4, y_back + facing * 0.26, z0 + 0.62)], 0.022, fillet=0.06)
        s3d.material(strap, "fabric", color="#151515")
        out.append(strap)
    head = s3d.fillet(s3d.box("crew_headrest", 0.30, 0.10, 0.16), 0.045, edges="side")
    s3d.material(head, "fabric", color="#25282c")
    out.append(s3d.at(head, x=x, y=yb, z=z0 + 1.18))
    return out


def interior() -> list:
    """Обшивка, пол, плафоны, поручень, рации на зарядке и четыре сиденья (по два лицом друг к другу)."""
    out = []
    zf = CAV["z0"]
    y0, y1 = CAV["y0"], CAV["y1"]
    floor = s3d.box("crew_floor", 2 * (HW - WALL) - 0.01, y1 - y0 - 0.01, 0.012)
    s3d.material(floor, "aluminium", color="#8d9093", roughness=0.45)
    out.append(s3d.at(floor, y=(y0 + y1) / 2, z=zf))
    ceil = s3d.box("crew_ceiling", 2 * (HW - WALL) - 0.01, y1 - y0 - 0.01, 0.012)
    s3d.material(ceil, "fabric", color="#8d9093")
    out.append(s3d.at(ceil, y=(y0 + y1) / 2, z=CAV["z1"] - 0.012))
    for yy in (y0 + 0.006, y1 - 0.006):
        wall = s3d.box("crew_wall_trim", 2 * (HW - WALL) - 0.01, 0.012, CAV["z1"] - zf - 0.02)
        s3d.material(wall, "plastic", color="#3b3e42", roughness=0.65)
        out.append(s3d.at(wall, y=yy, z=zf + 0.01))
    for sx in (1, -1):
        for ya, yb in ((y0 + 0.012, D["y0"] - 0.002), (D["y1"] + 0.002, y1 - 0.012)):
            side = s3d.box("crew_side_trim", 0.012, yb - ya, CAV["z1"] - zf - 0.02)
            s3d.material(side, "plastic", color="#3b3e42", roughness=0.65)
            out.append(s3d.at(side, x=sx * (HW - WALL - 0.006), y=(ya + yb) / 2, z=zf + 0.01))
    for y in (-0.95, -0.35):
        lamp = s3d.fillet(s3d.box("crew_ceiling_lamp", 0.34, 0.10, 0.025), 0.02, edges="side")
        lib.lens(lamp, "#f2f2ea")
        out.append(s3d.at(lamp, y=y, z=CAV["z1"] - 0.037))
    rail = s3d.wire("crew_grab_rail", [(0.0, y0 + 0.15, CAV["z1"] - 0.012), (0.0, y0 + 0.20, CAV["z1"] - 0.08),
                                       (0.0, y1 - 0.20, CAV["z1"] - 0.08), (0.0, y1 - 0.15, CAV["z1"] - 0.012)], 0.028, fillet=0.04)
    lib.chrome(rail)
    out.append(rail)
    for x in (-0.20, 0.20):
        dock = s3d.fillet(s3d.box("radio_charger", 0.08, 0.06, 0.10), 0.01, edges="side")
        lib.black_plastic(dock)
        radio = s3d.fillet(s3d.box("handheld_radio", 0.055, 0.035, 0.13), 0.012, edges="side")
        lib.black_plastic(radio)
        ant = s3d.wire("handheld_antenna", [(x + 0.012, y1 - 0.05, 2.36), (x + 0.012, y1 - 0.05, 2.50)], 0.008)
        lib.black_plastic(ant)
        out += [s3d.at(dock, x=x, y=y1 - 0.045, z=2.18), s3d.at(radio, x=x, y=y1 - 0.05, z=2.23), ant]
    for x in (-0.52, 0.52):
        out += seat(x, y0 + 0.015, 1.0) + seat(x, y1 - 0.015, -1.0)
    return out
