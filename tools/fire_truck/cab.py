"""Кабина «как КамАЗ после рестайлинга» (форма своя, без марок). Корпус, панели с зазорами, стёкла, крылья,
дворники и дефлекторы стоек — генератором кузовов «Проспекта» (cab_body.py); здесь — вставки решётки, бампер с фарами,
расширители и ниши арок, подножки, колпак с маячками, зеркала, ручки, мелочи и тёмный салон-заглушка."""
from __future__ import annotations

import bpy
import cab_body
import cab_interior
import lib
import shapes
import spec as S
from lib import s3d

F, B = S.CAB_FRONT, S.CAB_BACK
HW = S.CAB_W / 2


GRILLE_SLOTS = [(1.46, 1.50, 0.085), (1.30, 1.33, 0.085)]     # ширина, середина по высоте, высота щели
FACE_PANEL = dict(x=1.02, z0=1.13, z1=1.84)                    # откидная облицовка (решётка) — швы вокруг


def grille_inserts():
    """Чёрные вставки за щелями облицовки (облицовка — панель генератора) и по два ребра в каждой щели."""
    out = []
    for w, z, h in GRILLE_SLOTS:
        ins = s3d.fillet(s3d.box("grille_insert", w - 0.02, 0.02, h + 0.02), 0.012, edges="side")
        lib.black_plastic(ins)
        out.append(s3d.at(ins, y=F + 0.075, z=z - (h + 0.02) / 2))
        for dz in (-h / 5, h / 5):
            fin = s3d.fillet(s3d.box("grille_fin", w - 0.05, 0.035, 0.007), 0.003, edges="side")
            lib.black_plastic(fin)
            out.append(s3d.at(fin, y=F + 0.035, z=z + dz - 0.0035))
    return out


def bumper():
    """Белый пластиковый бампер с фарами, противотуманками, нишей номера и чёрной нижней губой."""
    b = S.BUMPER
    depth = b["y1"] - b["y0"]
    body = s3d.box("bumper", b["w"], depth, b["z1"] - b["z0"])
    s3d.fillet(body, 0.10, edges="side")
    s3d.fillet(body, 0.025, edges="top bottom")
    s3d.at(body, y=(b["y0"] + b["y1"]) / 2, z=b["z0"])
    fr = lib.front(b["y0"])
    lamps = []
    for sx in (-1, 1):
        hl = shapes.box_pts(sx * 0.70 - 0.19, sx * 0.70 + 0.19, 0.73, 0.88)
        s3d.pocket(body, shapes.outline(hl, 0.03), 0.05, on=fr)
        lensp = s3d.extrude("headlight", shapes.outline(shapes.box_pts(sx * 0.70 - 0.18, sx * 0.70 + 0.18, 0.74, 0.87), 0.025),
                            0.012, on=fr.offset(-0.04))
        lib.lens(lensp, "#e8eef0")
        reflector = s3d.extrude("reflector", shapes.outline(shapes.box_pts(sx * 0.70 - 0.18, sx * 0.70 + 0.18, 0.74, 0.87), 0.025),
                                0.004, on=fr.offset(-0.05))
        lib.chrome(reflector)
        ind = s3d.extrude("indicator", shapes.outline(shapes.box_pts(sx * 1.00 - 0.08, sx * 1.00 + 0.06, 0.75, 0.86), 0.02),
                          0.01, on=fr.offset(-0.002))
        lib.lens(ind, "#f0a020")
        fog_pts = shapes.box_pts(sx * 0.72 - 0.065, sx * 0.72 + 0.065, 0.55, 0.64)
        s3d.pocket(body, shapes.outline(fog_pts, 0.012), 0.03, on=fr)
        fog = s3d.extrude("foglight", shapes.outline(shapes.box_pts(sx * 0.72 - 0.058, sx * 0.72 + 0.058, 0.557, 0.633), 0.01),
                          0.01, on=fr.offset(-0.022))
        lib.lens(fog, "#f3f3ea")
        drl = s3d.fillet(s3d.box("drl_strip", 0.32, 0.008, 0.014), 0.006, edges="side")
        s3d.material(drl, "glass", color="#ffffff", opacity=0.85, emission=0.6)
        drl = s3d.at(drl, x=sx * 0.70, y=b["y0"] + 0.03, z=0.85)
        lamps += [lensp, reflector, ind, fog, drl]
    s3d.pocket(body, shapes.outline(shapes.box_pts(-0.28, 0.28, 0.50, 0.63), 0.01), 0.012, on=fr)
    s3d.pocket(body, shapes.outline(shapes.box_pts(-0.45, 0.45, 0.64, 0.71), 0.02), 0.06, on=fr)
    lib.paint_white(body)
    plate = s3d.box("plate_front", 0.52, 0.004, 0.112)
    s3d.material(plate, "painted_metal", color="#f0f0ea")
    pframe = s3d.fillet(s3d.box("plate_frame", 0.55, 0.006, 0.13), 0.01, edges="side")
    lib.black_plastic(pframe)
    lamps += [s3d.at(pframe, y=b["y0"] + 0.009, z=0.50), s3d.at(plate, y=b["y0"] + 0.006, z=0.509)]
    lip = s3d.fillet(s3d.box("bumper_lip", b["w"] - 0.30, 0.20, 0.06), 0.03, edges="side")
    lib.black_plastic(lip)
    lip = s3d.at(lip, y=b["y0"] + 0.14, z=b["z0"] - 0.03)
    hooks = []
    for sx in (-1, 1):
        hk = s3d.at(s3d.torus("tow_hook", 0.09, 0.022), x=sx * 0.42, y=b["y0"] - 0.03, z=0.47, rx=90)
        lib.steel_dark(hk)
        hooks.append(hk)
    return [body, lip] + lamps + hooks


arch_ring = shapes.arch_ring


def fenders():
    """Над передними колёсами: чёрные расширители арок и колёсные ниши; в нише подножки крыла — задняя
    стенка и рифлёная площадка; нижняя подножка — висячая, на двух кронштейнах под крылом."""
    f = S.FENDER
    out = []
    for sgn in (1, -1):
        flare = arch_ring("arch_flare", S.ARCH_R_F + 0.05, S.ARCH_R_F - 0.005, f["t"] + 0.03,
                          sgn * (HW - f["t"] / 2 + 0.01), S.YF, S.WHEEL_Z, keep=0.12)
        lib.black_plastic(flare)
        liner = arch_ring("wheel_house", S.ARCH_R_F + 0.02, S.ARCH_R_F + 0.005, 0.45, sgn * (HW - 0.38), S.YF,
                          S.WHEEL_Z, keep=0.0)
        lib.black_plastic(liner)
        z = S.STEPS_Z[1]
        back = s3d.box("step_back", 0.012, 0.18, 0.21)
        lib.black_plastic(back)
        tread = s3d.fillet(s3d.box("step", 0.12, 0.155, 0.022), 0.005, edges="side")
        lib.black_plastic(tread)
        out += [flare, liner, s3d.at(back, x=sgn * (HW - 0.115), y=S.STEP_Y, z=z - 0.01),
                s3d.at(tread, x=sgn * (HW - 0.06), y=S.STEP_Y, z=z)]
        low = s3d.fillet(s3d.box("step_low", 0.20, 0.17, 0.025), 0.006, edges="side")
        lib.black_plastic(low)
        out.append(s3d.at(low, x=sgn * (HW - 0.06), y=S.STEP_Y, z=S.FENDER["z0"] - 0.12))
        for dy in (-0.07, 0.07):
            strap = s3d.box("step_strap", 0.012, 0.025, 0.14)
            lib.steel_dark(strap)
            out.append(s3d.at(strap, x=sgn * (HW - 0.10), y=S.STEP_Y + dy, z=S.FENDER["z0"] - 0.10))
    return out


def roof_cap():
    """Белый колпак на крыше кабины с двумя синими маячками на передних углах."""
    pts = [(F + 0.20, S.CAB_ROOF - 0.03), (F + 0.34, S.CAP_TOP), (B - 0.03, S.CAP_TOP), (B - 0.03, S.CAB_ROOF - 0.03)]
    cap = s3d.extrude("roof_cap", s3d.poly(pts, fillet=[0, 0.09, 0.05, 0]), S.CAB_W - 0.10, both=True, on=lib.side(0))
    s3d.fillet(cap, 0.06, edges="top bottom")
    lib.paint_white(cap)
    out = [cap]
    for sx in (-1, 1):
        base = s3d.fillet(s3d.box("beacon_base", 0.46, 0.30, 0.03), 0.04, edges="side")
        lib.black_plastic(base)
        out.append(s3d.at(base, x=sx * (HW - 0.34), y=F + 0.58, z=S.CAP_TOP - 0.005))
        amber = s3d.fillet(s3d.box("cap_marker", 0.035, 0.06, 0.035), 0.01, edges="side")
        lib.lens(amber, "#f0a020")
        out.append(s3d.at(amber, x=sx * (HW - 0.06), y=F + 0.95, z=S.CAP_TOP - 0.09))
        dome = s3d.fillet(s3d.box("beacon", 0.44, 0.28, 0.11), 0.05, edges="side")
        s3d.fillet(dome, 0.035, edges="top")
        lib.lens(dome, "#2050d8")
        out.append(s3d.at(dome, x=sx * (HW - 0.34), y=F + 0.58, z=S.CAP_TOP + 0.02))
    return out


def mirrors():
    """Зеркала на кронштейнах у передних стоек: основное и широкоугольное; бордюрное справа сверху."""
    out = []
    for sgn in (1, -1):
        xa = sgn * (HW + 0.005)
        arm = s3d.wire("mirror_arm", [(xa, F + 0.55, 2.70), (sgn * (HW + 0.24), F + 0.52, 2.70),
                                      (sgn * (HW + 0.26), F + 0.52, 2.05), (xa, F + 0.55, 2.05)], 0.022, fillet=0.04)
        lib.black_plastic(arm)
        head = s3d.fillet(s3d.box("mirror", 0.085, 0.22, 0.40), 0.038, edges="side")
        s3d.fillet(head, 0.03, edges="top bottom")
        lib.black_plastic(head)
        head = s3d.at(head, x=sgn * (HW + 0.28), y=F + 0.495, z=2.27, rz=sgn * 10)
        glass_m = s3d.box("mirror_glass", 0.006, 0.19, 0.35)
        lib.chrome(glass_m)
        glass_m = s3d.at(glass_m, x=sgn * (HW + 0.28), y=F + 0.50 + 0.036, z=2.295, rz=sgn * 10 + 90)
        wide = s3d.fillet(s3d.box("mirror_wide", 0.08, 0.20, 0.18), 0.036, edges="side")
        s3d.fillet(wide, 0.025, edges="top bottom")
        lib.black_plastic(wide)
        wide = s3d.at(wide, x=sgn * (HW + 0.28), y=F + 0.495, z=2.075, rz=sgn * 10)
        wglass = s3d.box("mirror_wide_glass", 0.006, 0.17, 0.15)
        lib.chrome(wglass)
        wglass = s3d.at(wglass, x=sgn * (HW + 0.28), y=F + 0.50 + 0.04, z=2.09, rz=sgn * 10 + 90)
        out += [arm, head, glass_m, wide, wglass]
        for z in (2.70, 2.05):
            clamp = s3d.fillet(s3d.box("mirror_clamp", 0.05, 0.06, 0.06), 0.012, edges="side")
            lib.black_plastic(clamp)
            out.append(s3d.at(clamp, x=sgn * (HW + 0.012), y=F + 0.55, z=z - 0.03))
        for z in (2.48, 2.16):
            clamp = s3d.cylinder("mirror_pivot", 0.045, 0.05)
            lib.black_plastic(clamp)
            out.append(s3d.at(clamp, x=sgn * (HW + 0.26), y=F + 0.52, z=z - 0.025))
    kerb = s3d.fillet(s3d.box("mirror_kerb", 0.22, 0.07, 0.15), 0.03, edges="side")
    lib.black_plastic(kerb)
    out.append(s3d.at(kerb, x=-(HW - 0.20), y=F - 0.08, z=2.80, rx=-30))
    kerb_arm = s3d.wire("kerb_arm", [(-(HW - 0.20), F + 0.10, S.CAB_ROOF - 0.02), (-(HW - 0.20), F - 0.05, 2.90)], 0.018)
    lib.black_plastic(kerb_arm)
    out.append(kerb_arm)
    return out


def door_outer_details(sgn: float) -> list:
    """Наружные детали двери (едут с дверью): ручка в чашке, личинка замка, стойка форточки, петли (половинка двери)."""
    out = []
    w = S.SIDE_WIN
    post = s3d.box("vent_post", 0.012, 0.025, w["z1"] - w["z0"] - 0.04)
    lib.rubber(post)
    out.append(s3d.at(post, x=sgn * (HW - 0.012), y=w["y0"] + 0.24, z=w["z0"] + 0.02))
    cup = soft_cup = s3d.fillet(s3d.box("door_handle_cup", 0.012, 0.21, 0.07), 0.012, edges="side")
    lib.black_plastic(soft_cup)
    out.append(s3d.at(cup, x=sgn * (HW - 0.002), y=-1.86, z=1.805))
    h = s3d.fillet(s3d.box("door_handle", 0.03, 0.17, 0.04), 0.012, edges="side")
    lib.black_plastic(h)
    out.append(s3d.at(h, x=sgn * (HW + 0.008), y=-1.86, z=1.82))
    lock = s3d.cylinder("door_lock", 0.028, 0.012)
    lib.chrome(lock)
    out.append(s3d.at(lock, x=sgn * (HW + 0.004), y=-1.74, z=1.84, ry=90 * sgn))
    belt = s3d.box("door_belt_rubber", 0.012, w["y1"] - w["y0"] + 0.02, 0.016)
    lib.rubber(belt)
    out.append(s3d.at(belt, x=sgn * (HW + 0.002), y=(w["y0"] + w["y1"]) / 2, z=w["z0"] - 0.035))
    for z in (S.DOOR["z0"] + 0.32, S.DOOR["z1"] - 0.38):
        leaf = s3d.fillet(s3d.box("hinge_leaf_door", 0.012, 0.06, 0.09), 0.004, edges="side")
        lib.steel_dark(leaf)
        out.append(s3d.at(leaf, x=sgn * (HW + 0.004), y=S.DOOR["y0"] + 0.035, z=z))
    return out


def hinge_body_parts() -> list:
    """Петли кабины: половинки на стойке и оси (остаются на кабине)."""
    out = []
    px, py = cab_body.PIVOT
    for sgn in (1, -1):
        for z in (S.DOOR["z0"] + 0.32, S.DOOR["z1"] - 0.38):
            pin = s3d.cylinder("hinge_pin", 0.022, 0.10)
            lib.steel_dark(pin)
            leaf = s3d.fillet(s3d.box("hinge_leaf_body", 0.012, 0.05, 0.09), 0.004, edges="side")
            lib.steel_dark(leaf)
            out += [s3d.at(pin, x=sgn * px, y=py, z=z - 0.005), s3d.at(leaf, x=sgn * (HW + 0.004), y=py - 0.028, z=z)]
    return out


hinged = shapes.hinged
copy_tree = shapes.copy_tree


def handles_and_lamps():
    out = []
    for sgn in (1, -1):
        rep = s3d.fillet(s3d.box("side_repeater", 0.02, 0.09, 0.04), 0.015, edges="side")
        lib.lens(rep, "#f0a020")
        out.append(s3d.at(rep, x=sgn * (HW + 0.005), y=F + 0.30, z=1.30))
        grab = s3d.wire("grab_handle", [(sgn * (HW + 0.005), -1.66, 1.45), (sgn * (HW + 0.05), -1.66, 1.50),
                                        (sgn * (HW + 0.05), -1.66, 2.35), (sgn * (HW + 0.005), -1.66, 2.40)],
                        0.03, fillet=0.03)
        lib.black_plastic(grab)
        out.append(grab)
    return out


def cab_details():
    """Мелочи кабины: проекторы в фарах, щель воздухозаборника в бампере с перемычками, водостоки над
    дверями, оси дворников, громкоговоритель сирены под бампером, антенна на колпаке."""
    b = S.BUMPER
    out = []
    for sx in (-1, 1):
        for dx in (-0.09, 0.09):
            proj = s3d.cylinder("projector", 0.085, 0.02)
            lib.chrome(proj)
            out.append(s3d.at(proj, x=sx * 0.70 + dx, y=b["y0"] + 0.035, z=0.805, rx=90))
            lensr = s3d.cylinder("projector_lens", 0.06, 0.012)
            lib.lens(lensr, "#dfe8ee")
            out.append(s3d.at(lensr, x=sx * 0.70 + dx, y=b["y0"] + 0.025, z=0.805, rx=90))
            cup = s3d.shell(s3d.dome("projector_cup", 0.11, 0.05), 0.003, open="bottom")
            lib.chrome(cup)
            out.append(s3d.at(cup, x=sx * 0.70 + dx, y=b["y0"] + 0.04, z=0.805, rx=-90))
    for z in (0.69, 0.665):
        bar = s3d.fillet(s3d.box("bumper_intake_bar", 0.86, 0.02, 0.012), 0.005, edges="side")
        lib.black_plastic(bar)
        out.append(s3d.at(bar, y=b["y0"] + 0.02, z=z))
    for sx in (-1, 1):
        gut = s3d.fillet(s3d.box("rain_gutter", 0.018, B - F - 0.45, 0.022), 0.008, edges="side")
        lib.black_plastic(gut)
        out.append(s3d.at(gut, x=sx * (HW - 0.006), y=(F + 0.40 + B - 0.05) / 2, z=S.CAB_ROOF - 0.075))
    for sx in (-1, 1):
        nozzle = s3d.fillet(s3d.box("washer_nozzle", 0.03, 0.025, 0.018), 0.008, edges="side")
        lib.black_plastic(nozzle)
        out.append(s3d.at(nozzle, x=sx * 0.34, y=F - 0.006, z=1.875))
    spk = s3d.fillet(s3d.box("siren_speaker", 0.26, 0.16, 0.20), 0.03, edges="side")
    lib.black_plastic(spk)
    out.append(s3d.at(spk, x=-0.62, y=b["y1"] + 0.06, z=0.50))
    ant = s3d.wire("cab_antenna", [(0.85, B - 0.25, S.CAP_TOP), (0.85, B - 0.25, S.CAP_TOP + 0.45)], 0.007)
    lib.black_plastic(ant)
    base = s3d.cylinder("antenna_base", 0.05, 0.03)
    lib.black_plastic(base)
    out += [ant, s3d.at(base, x=0.85, y=B - 0.25, z=S.CAP_TOP)]
    return out


DOOR_OPEN_DEG = 68.0


def build() -> dict:
    """Кабина: общие детали — в обеих коллекциях; двери — на петлях: закрытые в «Целой», распахнутые на 68° —
    в «Отсеки открыты» (те же сетки)."""
    got = cab_body.build()
    parts = got["common"] + grille_inserts() + bumper() + fenders() + roof_cap() + mirrors() + handles_and_lamps() \
        + cab_details() + hinge_body_parts() + cab_interior.build()
    closed, opened = [], []
    px, py = cab_body.PIVOT
    for side, sgn in (("L", 1.0), ("R", -1.0)):
        door = got["door_" + side] + door_outer_details(sgn) + cab_interior.door_card_details(sgn)
        door_open = copy_tree(door)
        closed.append(hinged(f"Hinge_CabDoor_{side}_closed", door, (sgn * px, py), 0.0))
        opened.append(hinged(f"Hinge_CabDoor_{side}_open", door_open, (sgn * px, py), -sgn * DOOR_OPEN_DEG))
    return {"common": [s3d.group("Кабина", *parts)], "closed": closed, "open": opened}
