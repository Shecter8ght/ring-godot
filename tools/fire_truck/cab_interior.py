"""Салон кабины пожарной АЦ (виден сквозь светлые стёкла и при открытых дверях) и детали обивки дверей.

Метры, оси машины (X влево, Y назад, Z вверх). Водитель слева (+X). Пол кабины — FLOOR; наружные панели кабины —
листы генератора (cab_body.py), всё здесь держится не ближе 3 см к ним.
"""
from __future__ import annotations

import math

import lib
import spec as S
from lib import s3d

F, B = S.CAB_FRONT, S.CAB_BACK
HW = S.CAB_W / 2
FLOOR = 1.30
IN_X = HW - 0.10            # внутренние стенки салона
X_DRV = 0.70                # середина водительского сиденья (слева)
DOOR_T = 0.075


def fabric(ob, color="#2b2e33"):
    return s3d.material(ob, "fabric", color=color)


def trim(ob, color="#34373a"):
    return s3d.material(ob, "plastic", color=color, roughness=0.65)


def soft_box(name, w, d, h, r=0.03, top=True):
    b = s3d.box(name, w, d, h)
    s3d.fillet(b, min(r, w / 2.2, d / 2.2), edges="side")
    if top:
        s3d.fillet(b, min(r * 0.7, h / 2.5), edges="top")
    return b


def floor_and_walls() -> list:
    out = []
    mat = s3d.box("cab_floor_mat", 2 * IN_X + 0.02, (B - 0.05) - (F + 0.12), 0.016)
    s3d.material(mat, "rubber", color="#1c1c1c")
    out.append(s3d.at(mat, y=((B - 0.05) + (F + 0.12)) / 2, z=FLOOR))
    hump = soft_box("engine_hump", 0.72, (B - 0.08) - (F + 0.62), 0.38, r=0.10)
    trim(hump, "#2e3134")
    out.append(s3d.at(hump, y=((B - 0.08) + (F + 0.62)) / 2, z=FLOOR))
    back = s3d.box("cab_rear_trim", 2 * IN_X + 0.02, 0.02, 2.82 - FLOOR)
    trim(back, "#3b3e42")
    out.append(s3d.at(back, y=B - 0.045, z=FLOOR))
    head = s3d.fillet(s3d.box("headliner", 2 * IN_X + 0.02, (B - 0.04) - (F + 0.26), 0.02), 0.01, edges="side")
    fabric(head, "#8d9093")
    out.append(s3d.at(head, y=((B - 0.04) + (F + 0.26)) / 2, z=2.82))
    for sx in (-1, 1):
        kick = s3d.box("kick_panel", 0.025, (S.DOOR["y0"] - 0.03) - (F + 0.12), 1.92 - FLOOR)
        trim(kick)
        out.append(s3d.at(kick, x=sx * (IN_X + 0.012), y=((S.DOOR["y0"] - 0.03) + (F + 0.12)) / 2, z=FLOOR))
        bpil = s3d.box("b_pillar_trim", 0.025, (B - 0.04) - (S.DOOR["y1"] + 0.025), 2.82 - FLOOR)
        trim(bpil)
        out.append(s3d.at(bpil, x=sx * (IN_X + 0.012), y=((B - 0.04) + (S.DOOR["y1"] + 0.025)) / 2, z=FLOOR))
        sill = s3d.box("door_sill_plate", 0.10, S.DOOR["y1"] - S.DOOR["y0"] - 0.02, 0.012)
        lib.alu(sill)
        out.append(s3d.at(sill, x=sx * (IN_X + 0.02), y=(S.DOOR["y0"] + S.DOOR["y1"]) / 2, z=FLOOR - 0.004))
        pillar = s3d.wire("a_pillar_trim", [(sx * (IN_X + 0.02), F + 0.07, S.WS_BOTTOM + 0.04),
                                            (sx * (IN_X + 0.0), F + 0.20, S.WS_TOP + 0.03)], 0.06)
        trim(pillar)
        out.append(pillar)
        visor = soft_box("sun_visor", 0.40, 0.018, 0.19, r=0.02)
        fabric(visor, "#7d8084")
        out.append(s3d.at(visor, x=sx * 0.52, y=F + 0.27, z=2.62, rx=-12))
        vm = s3d.cylinder("visor_mount", 0.018, 0.05)
        trim(vm)
        out.append(s3d.at(vm, x=sx * 0.30, y=F + 0.27, z=2.79))
    dome = soft_box("dome_light", 0.22, 0.12, 0.025, r=0.02)
    lib.lens(dome, "#f2f2ea")
    out.append(s3d.at(dome, y=-2.10, z=2.795))
    radio = soft_box("radio_console", 0.46, 0.24, 0.12, r=0.025, top=False)
    trim(radio, "#222427")
    out.append(s3d.at(radio, y=F + 0.42, z=2.70))
    face = s3d.box("radio_face", 0.20, 0.006, 0.05)
    lib.lens(face, "#3d6b55")
    out.append(s3d.at(face, x=0.06, y=F + 0.54, z=2.735))
    for k in range(5):
        knob = s3d.cylinder("radio_knob", 0.018, 0.012)
        trim(knob, "#111111")
        out.append(s3d.at(knob, x=-0.15 + 0.035 * k, y=F + 0.546, z=2.76, rx=-90))
    ext = s3d.fillet(s3d.cylinder("cab_extinguisher", 0.13, 0.42), 0.03, edges="top")
    s3d.material(ext, "painted_metal", color="#c01818", roughness=0.4)
    out.append(s3d.at(ext, x=0.0, y=B - 0.16, z=FLOOR + 0.38))
    valve = s3d.at(s3d.cylinder("extinguisher_valve", 0.04, 0.06), x=0.0, y=B - 0.16, z=FLOOR + 0.80)
    lib.chrome(valve)
    out.append(valve)
    return out


def dashboard() -> list:
    """Панель приборов: корпус, щиток приборов водителя, центральная консоль, дефлекторы, бардачок."""
    out = []
    y0, y1 = F + 0.12, F + 0.54
    body = soft_box("dashboard", 2 * IN_X - 0.02, y1 - y0, 1.93 - 1.56, r=0.05)
    trim(body, "#2a2c2f")
    out.append(s3d.at(body, y=(y0 + y1) / 2, z=1.56))
    knee = s3d.fillet(s3d.box("dash_lower", 2 * IN_X - 0.10, 0.16, 0.14), 0.04, edges="side")
    trim(knee, "#232528")
    out.append(s3d.at(knee, y=y1 - 0.04, z=1.44))
    # щиток приборов водителя: козырёк и лицевая панель с приборами
    hood = soft_box("cluster_hood", 0.64, 0.22, 0.12, r=0.05)
    trim(hood, "#1f2123")
    out.append(s3d.at(hood, x=X_DRV - 0.08, y=y1 - 0.10, z=1.90))
    face_y = y1 + 0.004
    panel = s3d.box("cluster_face", 0.58, 0.01, 0.17)
    trim(panel, "#151617")
    out.append(s3d.at(panel, x=X_DRV - 0.08, y=face_y - 0.005, z=1.80))
    dials = [(X_DRV - 0.20, 1.885, 0.115), (X_DRV + 0.04, 1.885, 0.115)] + \
            [(X_DRV - 0.33 + 0.085 * k, 1.815, 0.05) for k in range(6)]
    for x, z, d in dials:
        dial = s3d.cylinder("gauge_face", d, 0.006)
        s3d.material(dial, "plastic", color="#0d0d0d", roughness=0.3)
        ring = s3d.tube("gauge_bezel", d + 0.012, d, 0.012)
        lib.chrome(ring)
        needle = s3d.box("gauge_needle", d * 0.42, 0.002, 0.004)
        s3d.material(needle, "plastic", color="#f2f2f2", emission=0.4)
        out += [s3d.at(dial, x=x, y=face_y, z=z, rx=-90), s3d.at(ring, x=x, y=face_y - 0.004, z=z, rx=-90),
                s3d.at(needle, x=x + d * 0.12, y=face_y + 0.007, z=z, ry=35)]
    # центральная консоль: радио, ряд клавиш, пульт спецсигналов сверху
    cons = soft_box("center_console", 0.46, 0.06, 0.30, r=0.02, top=False)
    trim(cons, "#1e2023")
    out.append(s3d.at(cons, x=0.05, y=y1 + 0.02, z=1.60))
    head_unit = s3d.box("head_unit", 0.18, 0.01, 0.05)
    lib.lens(head_unit, "#203040")
    out.append(s3d.at(head_unit, x=0.05, y=y1 + 0.051, z=1.80))
    for row, z in enumerate((1.70, 1.655)):
        for k in range(7):
            sw = soft_box("rocker", 0.026, 0.012, 0.036, r=0.004, top=False)
            s3d.material(sw, "plastic", color="#0f0f0f" if (k + row) % 3 else "#3a7d44", roughness=0.4)
            out.append(s3d.at(sw, x=-0.10 + 0.05 * k, y=y1 + 0.054, z=z))
    siren = soft_box("siren_controller", 0.30, 0.18, 0.07, r=0.02)
    trim(siren, "#18191b")
    out.append(s3d.at(siren, x=-0.12, y=y0 + 0.24, z=1.93))
    for k in range(6):
        btn = s3d.cylinder("siren_button", 0.026, 0.01)
        s3d.material(btn, "plastic", color=("#c02020", "#2050d0", "#e0a020")[k % 3], roughness=0.3)
        out.append(s3d.at(btn, x=-0.24 + 0.045 * k, y=y0 + 0.24, z=2.0))
    # дефлекторы обдува: круглые, хромированное кольцо, тёмная середина с ламелями
    for x in (X_DRV + 0.30, 0.38, -0.32, -0.80):
        ring = s3d.tube("vent_ring", 0.085, 0.07, 0.016)
        lib.chrome(ring)
        core = s3d.cylinder("vent_core", 0.07, 0.008)
        trim(core, "#0e0e0e")
        out += [s3d.at(ring, x=x, y=y1 - 0.004, z=1.86, rx=-90), s3d.at(core, x=x, y=y1 - 0.012, z=1.86, rx=-90)]
        for dz in (-0.018, 0.0, 0.018):
            fin = s3d.box("vent_fin", 0.062, 0.012, 0.004)
            trim(fin, "#202020")
            out.append(s3d.at(fin, x=x, y=y1 - 0.004, z=1.86 + dz))
    glove = soft_box("glovebox_lid", 0.46, 0.012, 0.18, r=0.02, top=False)
    trim(glove, "#2f3235")
    out.append(s3d.at(glove, x=-0.62, y=y1 + 0.003, z=1.60))
    latch = soft_box("glovebox_latch", 0.08, 0.012, 0.025, r=0.006, top=False)
    lib.chrome(latch)
    out.append(s3d.at(latch, x=-0.62, y=y1 + 0.012, z=1.73))
    return out


def driving_controls() -> list:
    """Рулевая колонка и руль (наклонён к водителю), подрулевые переключатели, педали, рычаг КПП на кожухе мотора."""
    out = []
    y1 = F + 0.54
    c0 = (X_DRV, y1 - 0.02, 1.70)
    c1 = (X_DRV, y1 + 0.22, 1.86)
    column = s3d.wire("steering_column", [c0, c1], 0.065)
    trim(column, "#1a1b1d")
    shroud = soft_box("column_shroud", 0.13, 0.20, 0.11, r=0.03)
    trim(shroud, "#202225")
    out += [column, s3d.at(shroud, x=X_DRV, y=y1 + 0.07, z=1.715, rx=34)]      # кожух — вдоль колонки, вверх к рулю
    wc = (X_DRV, y1 + 0.25, 1.88)
    tilt = -52.0
    rim = s3d.torus("steering_rim", 0.47, 0.034)
    s3d.material(rim, "plastic", color="#141414", roughness=0.55)
    hub = s3d.cylinder("steering_hub", 0.13, 0.05)
    s3d.material(hub, "plastic", color="#1b1b1b", roughness=0.5)
    out += [s3d.at(rim, x=wc[0], y=wc[1], z=wc[2], rx=tilt), s3d.at(hub, x=wc[0], y=wc[1], z=wc[2], rx=tilt)]
    ct, st = math.cos(math.radians(tilt)), math.sin(math.radians(tilt))
    for ang in (270.0, 30.0, 150.0):
        a = math.radians(ang)

        def on_wheel(r):                                 # точка в плоскости руля → наклон вокруг X
            lx, ly = r * math.cos(a), r * math.sin(a)
            return (wc[0] + lx, wc[1] + ly * ct, wc[2] + ly * st)
        spoke = s3d.wire("steering_spoke", [on_wheel(0.05), on_wheel(0.22)], 0.03)
        s3d.material(spoke, "plastic", color="#1b1b1b", roughness=0.5)
        out.append(spoke)
    for sx_ in (-1, 1):
        stalk = s3d.wire("column_stalk", [(X_DRV + sx_ * 0.05, y1 + 0.14, 1.78), (X_DRV + sx_ * 0.17, y1 + 0.16, 1.79)], 0.014)
        trim(stalk, "#151515")
        out.append(stalk)
    for k, x in enumerate((X_DRV - 0.16, X_DRV, X_DRV + 0.14)):
        w = 0.09 if k < 2 else 0.06
        pad = soft_box("pedal", w, 0.025, 0.10 if k < 2 else 0.16, r=0.01, top=False)
        s3d.material(pad, "rubber", color="#151515")
        arm = s3d.wire("pedal_arm", [(x, y1 - 0.02, 1.52), (x, y1 + 0.02, 1.42)], 0.016)
        lib.steel_dark(arm)
        out += [s3d.at(pad, x=x, y=y1 + 0.03, z=FLOOR + 0.06, rx=-30), arm]
    gb = (0.27, F + 0.98, FLOOR + 0.38)
    boot = s3d.cone("gear_boot", 0.12, 0.10, d2=0.03)
    s3d.material(boot, "rubber", color="#121212")
    lever = s3d.wire("gear_lever", [gb, (0.24, gb[1] - 0.08, gb[2] + 0.36)], 0.018)
    lib.chrome(lever)
    knob = s3d.sphere("gear_knob", 0.055)
    s3d.material(knob, "plastic", color="#101010", roughness=0.4)
    out += [s3d.at(boot, x=gb[0], y=gb[1], z=gb[2]), lever, s3d.at(knob, x=0.24, y=gb[1] - 0.08, z=gb[2] + 0.36 - 0.027)]
    brake = s3d.wire("park_brake", [(0.15, F + 0.66, 1.80), (0.15, F + 0.72, 1.92)], 0.014)
    lib.chrome(brake)
    knob2 = s3d.at(s3d.sphere("park_brake_knob", 0.035), x=0.15, y=F + 0.72, z=1.90)
    s3d.material(knob2, "plastic", color="#b01010", roughness=0.4)
    out += [brake, knob2]
    return out


def seat(name: str, x: float, suspension: bool) -> list:
    """Сиденье: основание (у водителя — подвеска с гармошкой), подушка, спинка с наклоном, подголовник, боковины."""
    out = []
    yc = B - 0.44
    z_base = FLOOR + (0.22 if suspension else 0.18)
    if suspension:
        bellows = s3d.fillet(s3d.box(name + "_bellows", 0.36, 0.34, z_base - FLOOR), 0.03, edges="side")
        s3d.material(bellows, "rubber", color="#141414")
        rails = [s3d.at(s3d.box(name + "_rail", 0.03, 0.46, 0.02), x=x + d, y=yc, z=FLOOR) for d in (-0.15, 0.15)]
        for r_ in rails:
            lib.steel_dark(r_)
        out += [s3d.at(bellows, x=x, y=yc, z=FLOOR)] + rails
    else:
        frame = s3d.fillet(s3d.box(name + "_base", 0.40, 0.40, z_base - FLOOR), 0.02, edges="side")
        lib.steel_dark(frame)
        out.append(s3d.at(frame, x=x, y=yc, z=FLOOR))
    cush = soft_box(name + "_cushion", 0.52, 0.50, 0.13, r=0.06)
    fabric(cush)
    out.append(s3d.at(cush, x=x, y=yc, z=z_base))
    for sx_ in (-1, 1):
        bol = soft_box(name + "_bolster", 0.07, 0.46, 0.07, r=0.03)
        fabric(bol, "#25282c")
        out.append(s3d.at(bol, x=x + sx_ * 0.235, y=yc, z=z_base + 0.10))
    back = soft_box(name + "_back", 0.52, 0.14, 0.64, r=0.06)
    fabric(back)
    out.append(s3d.at(back, x=x, y=B - 0.15, z=z_base + 0.10, rx=-11))
    head = soft_box(name + "_headrest", 0.30, 0.11, 0.18, r=0.05)
    fabric(head, "#25282c")
    out.append(s3d.at(head, x=x, y=B - 0.10, z=z_base + 0.78, rx=-11))
    for d in (-0.08, 0.08):
        post = s3d.cylinder(name + "_headrest_post", 0.012, 0.06)
        lib.chrome(post)
        out.append(s3d.at(post, x=x + d, y=B - 0.11, z=z_base + 0.73))
    belt = s3d.wire(name + "_belt", [(x + 0.30 * (1 if x > 0 else -1), B - 0.10, z_base + 0.72),
                                     (x - 0.05 * (1 if x > 0 else -1), B - 0.30, z_base + 0.30),
                                     (x - 0.27 * (1 if x > 0 else -1), B - 0.36, z_base + 0.10)], 0.012, fillet=0.06)
    fabric(belt, "#151515")
    out.append(belt)
    return out


def door_card_details(sx: float) -> list:
    """Обивка двери изнутри (левая sx = 1, правая −1): подлокотник, внутренняя ручка, ручка стеклоподъёмника,
    динамик, карман, кнопка замка. Сторона двери — по sx, всё в осях машины (дверь закрыта)."""
    xc = sx * (HW - DOOR_T)
    inward = -sx
    d = S.DOOR
    yc = (d["y0"] + d["y1"]) / 2
    out = []
    arm = soft_box("door_armrest", 0.06, 0.42, 0.06, r=0.02)
    trim(arm, "#2a2c2f")
    out.append(s3d.at(arm, x=xc + inward * 0.03, y=yc + 0.04, z=1.72))
    handle = soft_box("door_inner_handle", 0.025, 0.12, 0.03, r=0.008)
    lib.chrome(handle)
    out.append(s3d.at(handle, x=xc + inward * 0.012, y=d["y1"] - 0.20, z=1.86))
    bezel = soft_box("door_handle_bezel", 0.008, 0.16, 0.06, r=0.012, top=False)
    trim(bezel, "#1d1f21")
    out.append(s3d.at(bezel, x=xc + inward * 0.004, y=d["y1"] - 0.20, z=1.845))
    hub = s3d.cylinder("window_crank_hub", 0.05, 0.02)
    trim(hub, "#1a1a1a")
    crank = s3d.box("window_crank_arm", 0.012, 0.11, 0.02)
    trim(crank, "#1a1a1a")
    knob = s3d.cylinder("window_crank_knob", 0.022, 0.04)
    trim(knob, "#101010")
    out += [s3d.at(hub, x=xc, y=yc - 0.10, z=1.58, ry=-90 * sx),
            s3d.at(crank, x=xc + inward * 0.02, y=yc - 0.06, z=1.57),
            s3d.at(knob, x=xc + inward * 0.02, y=yc - 0.01, z=1.58, ry=-90 * sx)]
    spk = s3d.cylinder("door_speaker", 0.16, 0.012)
    trim(spk, "#151515")
    grill = s3d.cylinder("door_speaker_grille", 0.13, 0.006)
    s3d.material(grill, "brushed_steel", color="#55585c")
    out += [s3d.at(spk, x=xc, y=d["y0"] + 0.22, z=1.45, ry=-90 * sx),
            s3d.at(grill, x=xc + inward * 0.012, y=d["y0"] + 0.22, z=1.45, ry=-90 * sx)]
    pocket = soft_box("door_pocket", 0.035, 0.40, 0.13, r=0.012, top=False)
    trim(pocket, "#26282b")
    out.append(s3d.at(pocket, x=xc + inward * 0.018, y=yc + 0.20, z=1.36))
    lock = s3d.cylinder("door_lock_knob", 0.012, 0.035)
    lib.chrome(lock)
    out.append(s3d.at(lock, x=xc + inward * 0.03, y=d["y1"] - 0.08, z=1.96))
    return out


def build() -> list:
    return floor_and_walls() + dashboard() + driving_controls() + seat("seat_driver", X_DRV, True) + \
        seat("seat_commander", -X_DRV, False)
