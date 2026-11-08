"""Крыша надстройки: рифлёный настил, лоток с четырьмя всасывающими рукавами (гофра, головки),
трёхколенная лестница на роликах, лафетный ствол, поручни, фары-искатели."""
from __future__ import annotations

import lib
import spec as S
from lib import s3d

HW = S.BODY_W / 2
TOP = S.BAND[1]


def deck():
    """Настил крыши: алюминиевый лист; на проходе между лотком рукавов и лестницей — рифление «чечевица»
    (бугорки накрест через один), отдельной сеткой без булевых."""
    y0, y1 = S.BODY_FRONT + 0.06, S.BODY_BACK - 0.36
    plate = s3d.box("roof_deck", S.BODY_W - 0.12, y1 - y0, 0.006)
    plate = s3d.at(plate, y=(y0 + y1) / 2, z=TOP - 0.004)
    lib.alu(plate)
    x0, x1 = -0.34, 0.16
    wy0, wy1 = S.BODY_FRONT + 0.25, S.BODY_BACK - 0.55
    px, py = 0.045, 0.045
    nx, ny = int((x1 - x0) / px), int((wy1 - wy0) / py)
    bumps = []
    # бугорок строится уже повёрнутым профилем: merge в sand3d 1.6.3 неверно сводит повёрнутые копии
    import math as _m
    for turn in (45, -45):
        c, s_ = _m.cos(_m.radians(turn)), _m.sin(_m.radians(turn))
        rect = [(-0.003, -0.012), (0.003, -0.012), (0.003, 0.012), (-0.003, 0.012)]
        lug = s3d.extrude("tread_lug", s3d.poly([(x * c - y * s_, x * s_ + y * c) for x, y in rect], fillet=0.0025), 0.0022)
        frames = []
        for i in range(nx):
            for j in range(ny):
                if (i + j) % 2 == (0 if turn > 0 else 1):
                    frames.append(s3d.Frame((x0 + (i + 0.5) * px, wy0 + (j + 0.5) * py, TOP + 0.002)))
        bumps += s3d.at(lug, on=frames)
    tread = s3d.merge(*bumps)
    lib.alu(tread)
    return [plate, tread]


def suction_hose(length: float):
    """Всасывающий рукав: гофра (кольца) вдоль Z, на концах — алюминиевые головки с рожками."""
    r = S.HOSE_D / 2
    pitch = 0.035
    n = int((length - 0.24) / pitch)
    prof = [(0.0, 0.12), (r - 0.006, 0.12)]
    for k in range(n):
        z = 0.12 + k * pitch
        prof += [(r, z + 0.25 * pitch), (r, z + 0.55 * pitch), (r - 0.006, z + pitch)]
    prof += [(0.0, 0.12 + n * pitch)]
    hose = s3d.revolve("suction_hose", s3d.poly(prof))
    lib.rubber(hose)
    heads = []
    for z0, flip in ((0.0, 1), (length, -1)):
        head = s3d.cylinder("hose_head", S.HOSE_D + 0.025, 0.12)
        lugs = s3d.at(s3d.box("head_lug", 0.05, 0.025, 0.05), on=s3d.ring(2, (S.HOSE_D + 0.025) / 2 + 0.02,
                                                                        on=s3d.Frame((0, 0, 0.035))))
        s3d.join(head, lugs)
        lib.alu(head)
        heads.append(s3d.at(head, z=z0 if flip > 0 else z0 - 0.12))
    return s3d.group("hose", hose, *heads)


def hose_tray():
    y0, y1 = S.HOSE_Y
    length = y1 - y0
    out = []
    tray = s3d.box("hose_tray", 4 * (S.HOSE_D + 0.02) + 0.04, length - 0.3, 0.025)
    lib.alu(tray)
    xc = HW - 0.20 - 2 * (S.HOSE_D + 0.02)
    out.append(s3d.at(tray, x=xc, y=(y0 + y1) / 2, z=TOP))
    for k in range(S.HOSE_N):
        x = xc + (k - (S.HOSE_N - 1) / 2) * (S.HOSE_D + 0.02)
        h = suction_hose(length)
        out.append(s3d.at(h, x=x, y=y0, z=TOP + 0.025 + S.HOSE_D / 2, rx=-90))
    for y in (y0 + 0.4, (y0 + y1) / 2, y1 - 0.4):
        strap = s3d.box("hose_strap", 4 * (S.HOSE_D + 0.02) + 0.06, 0.05, 0.006)
        lib.black_plastic(strap)
        out.append(s3d.at(strap, x=xc, y=y, z=TOP + 0.025 + S.HOSE_D + 0.002))
        for sx in (-1, 1):
            post = s3d.box("tray_post", 0.02, 0.05, S.HOSE_D + 0.03)
            lib.alu(post)
            out.append(s3d.at(post, x=xc + sx * (2 * (S.HOSE_D + 0.02) + 0.03), y=y, z=TOP))
    return out


RUNG_PITCH = 0.28


def _rail_profile(xc: float, sx: float) -> list:
    """Сечение тетивы-швеллера (X, Z): стенка снаружи, полки и загибы внутрь лестницы; высота 75, ширина 30, стенка 4 мм."""
    xo, xi = 0.015, -0.015
    t, lip, h = 0.004, 0.012, 0.075
    pts = [(xo, 0.0), (xo, h), (xi, h), (xi, h - lip), (xi + t, h - lip), (xi + t, h - t), (xo - t, h - t),
           (xo - t, t), (xi + t, t), (xi + t, lip), (xi, lip), (xi, 0.0)]
    return [(xc + sx * x, z) for x, z in pts]


def ladder_section(name: str, w: float, length: float):
    """Колено лестницы вдоль +Y от 0: тетивы-швеллеры, круглые ступени с фланцами у тетив, заглушки на концах."""
    caps = []
    for sx in (-1, 1):
        for y in (0.0, length - 0.03):
            cap = s3d.fillet(s3d.box(name + "_end_cap", 0.032, 0.03, 0.077), 0.006, edges="side")
            caps.append(s3d.at(cap, x=sx * (w / 2 - 0.015), y=y + 0.015, z=-0.001))
    parts = [caps[0]]                                    # первая деталь без рамки: at() двигает в осях мира
    for sx in (-1, 1):
        prof = [(-x, z) for x, z in _rail_profile(sx * (w / 2 - 0.015), sx)]
        parts.append(s3d.extrude(name + "_rail", s3d.poly(prof, fillet=[0.0015] * len(prof)), length, on=lib.rear(0.0)))
    n = int((length - 0.12) / RUNG_PITCH) + 1
    for k in range(n):
        y = 0.10 + k * RUNG_PITCH
        parts.append(s3d.extrude(name + "_rung", s3d.circle(0.03), w - 0.05, both=True, on=lib.side(0, 1, y, 0.0375)))
        for sx in (-1, 1):
            parts.append(s3d.extrude(name + "_rung_flange", s3d.circle(0.046), 0.004, both=True,
                                     on=lib.side(sx * (w / 2 - 0.032), 1, y, 0.0375)))
    s3d.join(parts[0], *parts[1:], *caps[1:])
    lib.alu(parts[0])
    return parts[0]


def ladder():
    """Трёхколенная лестница на опорах с роликами: колена одно в другом, направляющие на концах, блок и трос
    выдвижения, защёлки, жёлтые прижимы на опорах."""
    l = S.LADDER
    length = l["y1"] - l["y0"]
    out = []
    z = TOP + 0.10
    widths = (l["w"], l["w"] - 0.06, l["w"] - 0.12)
    for k, w in enumerate(widths):
        sec = ladder_section(f"ladder_{k + 1}", w, length - 0.1 * k)
        out.append(s3d.at(sec, x=l["x"], y=l["y0"] + 0.05 * k, z=z + 0.078 * k))
    for k in range(2):
        for y in (l["y0"] + 0.05 * (k + 1) + 0.05, l["y1"] - 0.10 - 0.05 * k):
            for sx in (-1, 1):
                g = s3d.fillet(s3d.box("ladder_guide", 0.02, 0.07, 0.10), 0.005, edges="side")
                lib.alu(g)
                out.append(s3d.at(g, x=l["x"] + sx * (widths[k] / 2 - 0.002), y=y, z=z + 0.078 * k + 0.02))
    yp = l["y1"] - 0.08
    pulley = s3d.extrude("ladder_pulley", s3d.circle(0.07), 0.025, both=True, on=lib.side(l["x"], 1, yp, z + 0.11))
    lib.steel_dark(pulley)
    axle = s3d.extrude("ladder_pulley_axle", s3d.circle(0.016), widths[0] - 0.04, both=True, on=lib.side(l["x"], 1, yp, z + 0.11))
    lib.steel_dark(axle)
    rope = s3d.wire("ladder_rope", [(l["x"], l["y0"] + 0.25, z + 0.20), (l["x"], yp - 0.02, z + 0.18),
                                    (l["x"], yp + 0.04, z + 0.15), (l["x"], yp - 0.02, z + 0.04),
                                    (l["x"], l["y0"] + 0.60, z + 0.03)], 0.011, fillet=0.03)
    s3d.material(rope, "fabric", color="#c9b58a")
    out += [pulley, axle, rope]
    for sx in (-1, 1):
        pawl = s3d.fillet(s3d.box("ladder_pawl", 0.025, 0.08, 0.05), 0.008, edges="side")
        lib.black_plastic(pawl)
        out.append(s3d.at(pawl, x=l["x"] + sx * (widths[1] / 2 + 0.012), y=l["y0"] + 0.30, z=z + 0.095))
    # опоры с роликами спереди и сзади, прижимы поверх верхнего колена
    for y in (l["y0"] + 0.30, l["y1"] - 0.35):
        beam = s3d.fillet(s3d.box("ladder_support", l["w"] + 0.10, 0.06, 0.05), 0.008, edges="side")
        lib.steel_dark(beam)
        out.append(s3d.at(beam, x=l["x"], y=y, z=TOP + 0.05))
        for sx in (-1, 1):
            leg = s3d.fillet(s3d.box("support_leg", 0.04, 0.06, 0.06), 0.006, edges="side")
            lib.steel_dark(leg)
            out.append(s3d.at(leg, x=l["x"] + sx * (l["w"] / 2 + 0.03), y=y, z=TOP))
            roller = s3d.extrude("roller", s3d.circle(0.06), 0.05, both=True,
                                 on=lib.side(l["x"] + sx * (l["w"] / 2 + 0.035), 1, y, TOP + 0.13))
            lib.black_plastic(roller)
            out.append(roller)
        x0 = l["x"] + (l["w"] / 2 + 0.03)
        clamp = s3d.wire("ladder_clamp", [(x0, y + 0.04, TOP + 0.06), (x0, y + 0.04, z + 0.27),
                                          (l["x"] - widths[2] / 2 + 0.05, y + 0.04, z + 0.27),
                                          (l["x"] - widths[2] / 2 + 0.05, y + 0.04, z + 0.225)], 0.018, fillet=0.03)
        s3d.material(clamp, "painted_metal", color="#e0b020", roughness=0.4)
        knob = s3d.cylinder("ladder_clamp_knob", 0.05, 0.03)
        lib.black_plastic(knob)
        out += [clamp, s3d.at(knob, x=x0, y=y + 0.04, z=z + 0.28)]
    return out


def monitor():
    """Лафетный ствол с электроприводом: фланец с болтами, нижний корпус с мотором поворота, стойка, шарнир подъёма
    с мотором, колено, ствол с кольцами жёсткости, насадок с рукояткой распыла и резиновым бампером, румпель, кабель."""
    x, y = S.MONITOR["x"], S.MONITOR["y"]
    parts = []
    flange = s3d.cylinder("monitor_flange", 0.26, 0.022)
    lib.paint_white(flange)
    bolts = s3d.at(s3d.extrude("monitor_bolt", s3d.polygon(6, 0.022), 0.012), on=s3d.ring(8, 0.11, on=s3d.Frame((0, 0, 0.022))))
    for b_ in bolts:
        lib.steel_dark(b_)
    lower = s3d.at(s3d.fillet(s3d.cylinder("monitor_lower", 0.20, 0.11), 0.025, edges="top"), z=0.022)
    lib.paint_white(lower)
    drive1 = s3d.extrude("monitor_drive_rot", s3d.circle(0.10), 0.17, on=lib.side(0.09, 1, 0.0, 0.085))
    s3d.fillet(drive1, 0.015, edges="top")
    lib.paint_white(drive1)
    cap1 = s3d.extrude("monitor_drive_cap", s3d.circle(0.082), 0.025, on=lib.side(0.26, 1, 0.0, 0.085))
    lib.black_plastic(cap1)
    riser = s3d.at(s3d.cylinder("monitor_riser", 0.095, 0.10), z=0.13)
    lib.paint_white(riser)
    joint = s3d.extrude("monitor_joint", s3d.circle(0.15), 0.17, both=True, on=lib.side(0.0, 1, -0.01, 0.26))
    s3d.fillet(joint, 0.02, edges="top bottom")
    lib.paint_white(joint)
    drive2 = s3d.extrude("monitor_drive_elev", s3d.circle(0.09), 0.12, on=lib.side(-0.085, -1, -0.01, 0.26))
    s3d.fillet(drive2, 0.015, edges="top")
    lib.paint_white(drive2)
    cap2 = s3d.extrude("monitor_drive_cap2", s3d.circle(0.074), 0.022, on=lib.side(-0.205, -1, -0.01, 0.26))
    lib.black_plastic(cap2)
    parts += [flange, lower, drive1, cap1, riser, joint, drive2, cap2] + bolts
    # ствол наклонён вперёд и чуть вверх (как прежде, rx = 85)
    import math as _m
    d = (0.0, -_m.sin(_m.radians(85)), _m.cos(_m.radians(85)))
    p0 = (0.0, -0.06, 0.26)

    def along(t):
        return (p0[0] + d[0] * t, p0[1] + d[1] * t, p0[2] + d[2] * t)
    barrel = s3d.at(s3d.cylinder("monitor_barrel", 0.088, 0.40), x=p0[0], y=p0[1], z=p0[2], rx=85)
    lib.paint_white(barrel)
    parts.append(barrel)
    for t in (0.13, 0.27):
        q = along(t)
        ring = s3d.tube("monitor_barrel_ring", 0.102, 0.086, 0.025)
        lib.paint_white(ring)
        parts.append(s3d.at(ring, x=q[0], y=q[1], z=q[2], rx=85))
    q = along(0.40)
    noz_prof = [(0.0, 0.0), (0.047, 0.0), (0.052, 0.02), (0.062, 0.04), (0.062, 0.11), (0.054, 0.13), (0.046, 0.17),
                (0.036, 0.20), (0.0, 0.20)]
    nozzle = s3d.revolve("monitor_nozzle", s3d.poly(noz_prof, fillet=[0, 0.004, 0.008, 0.006, 0.006, 0.01, 0.008, 0.004, 0]))
    lib.alu(nozzle)
    parts.append(s3d.at(nozzle, x=q[0], y=q[1], z=q[2], rx=85))
    for t in (0.06, 0.085, 0.11):
        rib = s3d.tube("monitor_nozzle_rib", 0.132, 0.12, 0.008)
        lib.black_plastic(rib)
        qq = along(0.40 + t)
        parts.append(s3d.at(rib, x=qq[0], y=qq[1], z=qq[2], rx=85))
    qb = along(0.585)
    bumper = s3d.torus("monitor_nozzle_bumper", 0.098, 0.026)
    lib.rubber(bumper)
    parts.append(s3d.at(bumper, x=qb[0], y=qb[1], z=qb[2], rx=85))
    a, b_ = along(0.10), along(0.30)
    tiller = s3d.wire("monitor_tiller", [(0.05, a[1], a[2] + 0.02), (0.13, a[1] - 0.02, a[2] + 0.02),
                                         (0.13, b_[1] + 0.02, b_[2] + 0.02), (0.05, b_[1], b_[2] + 0.02)], 0.024, fillet=0.03)
    lib.black_plastic(tiller)
    cable = s3d.wire("monitor_cable", [(0.27, 0.0, 0.085), (0.32, 0.06, 0.03), (0.32, 0.40, 0.012)], 0.014, fillet=0.04)
    lib.black_plastic(cable)
    parts += [tiller, cable]
    g = s3d.group("monitor", *parts)
    return [s3d.at(g, x=x, y=y, z=TOP)]


def rails():
    """Поручни по краям крыши: труба на стойках."""
    out = []
    y0, y1 = S.BODY_FRONT + 0.25, S.BODY_BACK - 0.45
    for sx in (-1, 1):
        x = sx * (HW - 0.05)
        pts = [(x, y0, TOP + 0.005), (x, y0 + 0.05, TOP + 0.13), (x, y1 - 0.05, TOP + 0.13), (x, y1, TOP + 0.005)]
        out.append(s3d.wire("roof_rail", pts, 0.03, fillet=0.06))
        n = int((y1 - y0) / 1.0)
        for k in range(1, n):
            post = s3d.cylinder("rail_post", 0.025, 0.13)
            out.append(s3d.at(post, x=x, y=y0 + k * (y1 - y0) / n, z=TOP))
    for o in out:
        lib.alu(o)
    return out


def floodlights():
    out = []
    for sx in (-1, 1):
        body = s3d.fillet(s3d.box("floodlight", 0.20, 0.10, 0.14), 0.03, edges="side")
        lib.black_plastic(body)
        lens = s3d.box("floodlight_lens", 0.17, 0.006, 0.11)
        lib.lens(lens, "#f5f5ee")
        bracket = s3d.cylinder("flood_post", 0.03, 0.10)
        lib.black_plastic(bracket)
        x, y = sx * (HW - 0.30), S.BODY_BACK - 0.55
        out += [s3d.at(bracket, x=x, y=y, z=TOP), s3d.at(body, x=x, y=y, z=TOP + 0.10),
                s3d.at(lens, x=x, y=y + 0.052, z=TOP + 0.115)]
    bar = s3d.fillet(s3d.box("work_light_bar", 0.50, 0.05, 0.05), 0.015, edges="side")
    lib.black_plastic(bar)
    out.append(s3d.at(bar, x=-0.10, y=S.BODY_BACK - 0.40, z=TOP + 0.12))
    for dx in (-0.14, 0.14):
        post = s3d.cylinder("work_light_post", 0.03, 0.12)
        lib.black_plastic(post)
        lamp = s3d.fillet(s3d.cylinder("work_light", 0.13, 0.09), 0.02, edges="top bottom")
        lib.black_plastic(lamp)
        lens_ = s3d.cylinder("work_light_lens", 0.11, 0.008)
        lib.lens(lens_, "#f5f5ee")
        out += [s3d.at(post, x=-0.10 + dx, y=S.BODY_BACK - 0.40, z=TOP),
                s3d.at(lamp, x=-0.10 + dx, y=S.BODY_BACK - 0.43, z=TOP + 0.235, rx=-90),
                s3d.at(lens_, x=-0.10 + dx, y=S.BODY_BACK - 0.34, z=TOP + 0.235, rx=-90)]
    ant = s3d.wire("antenna", [(0.6, S.BODY_FRONT + 0.4, TOP), (0.6, S.BODY_FRONT + 0.4, TOP + 0.55)], 0.008)
    lib.black_plastic(ant)
    out.append(ant)
    return out


def build() -> dict:
    parts = deck() + hose_tray() + ladder() + monitor() + rails() + floodlights()
    return {"common": [s3d.group("Крыша", *parts)]}
