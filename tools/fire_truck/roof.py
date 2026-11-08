"""Крыша надстройки: рифлёный настил, лоток с четырьмя всасывающими рукавами (гофра, головки),
трёхколенная лестница на роликах, лафетный ствол, поручни, фары-искатели."""
from __future__ import annotations

import lib
import spec as S
from lib import s3d

HW = S.BODY_W / 2
TOP = S.BAND[1]


def deck():
    """Настил крыши: алюминиевый лист с ромбовидным рифлением (бугорки), чуть ниже кромки полосы."""
    y0, y1 = S.BODY_FRONT + 0.06, S.BODY_BACK - 0.36
    plate = s3d.box("roof_deck", S.BODY_W - 0.12, y1 - y0, 0.006)
    plate = s3d.at(plate, y=(y0 + y1) / 2, z=TOP - 0.004)
    lib.alu(plate)
    return [plate]


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


def ladder_section(name: str, w: float, length: float):
    """Колено лестницы: две тетивы-короба и круглые ступени через 0,34 м, лежит вдоль +Y от 0."""
    parts = []
    for sx in (-1, 1):
        rail = s3d.fillet(s3d.box(name + "_rail", 0.03, length, 0.075), 0.006, edges="side")
        parts.append(s3d.at(rail, x=sx * (w / 2 - 0.015), y=length / 2))
    n = int(length / 0.34)
    for k in range(n):
        parts.append(s3d.extrude(name + "_rung", s3d.circle(0.028), w - 0.06, both=True,
                                 on=lib.side(0, 1, 0.17 + k * 0.34, 0.037)))
    s3d.join(parts[0], *parts[1:])
    lib.alu(parts[0])
    return parts[0]


def ladder():
    l = S.LADDER
    length = l["y1"] - l["y0"]
    out = []
    z = TOP + 0.10
    for k, w in enumerate((l["w"], l["w"] - 0.06, l["w"] - 0.12)):
        sec = ladder_section(f"ladder_{k + 1}", w, length - 0.1 * k)
        out.append(s3d.at(sec, x=l["x"], y=l["y0"] + 0.05 * k, z=z + 0.078 * k))
    # опоры с роликами спереди и сзади
    for y in (l["y0"] + 0.30, l["y1"] - 0.35):
        beam = s3d.box("ladder_support", l["w"] + 0.10, 0.06, 0.05)
        lib.steel_dark(beam)
        out.append(s3d.at(beam, x=l["x"], y=y, z=TOP + 0.05))
        for sx in (-1, 1):
            leg = s3d.box("support_leg", 0.04, 0.06, 0.06)
            lib.steel_dark(leg)
            out.append(s3d.at(leg, x=l["x"] + sx * (l["w"] / 2 + 0.03), y=y, z=TOP))
            roller = s3d.extrude("roller", s3d.circle(0.06), 0.05, both=True,
                                 on=lib.side(l["x"] + sx * (l["w"] / 2 + 0.035), 1, y, TOP + 0.13))
            lib.black_plastic(roller)
            out.append(roller)
    return out


def monitor():
    """Лафетный ствол: фланец на крыше, поворотная часть с приводом, колено, ствол с насадком."""
    x, y = S.MONITOR["x"], S.MONITOR["y"]
    base = s3d.cylinder("monitor_base", 0.30, 0.06)
    turret = s3d.at(s3d.fillet(s3d.cylinder("monitor_turret", 0.22, 0.20), 0.03, edges="top"), z=0.06)
    drive = s3d.at(s3d.fillet(s3d.box("monitor_drive", 0.18, 0.22, 0.16), 0.03, edges="side top"), x=0.16, z=0.08)
    s3d.join(base, turret, drive)
    lib.paint_white(base)
    elbow = s3d.wire("monitor_elbow", [(0, 0, 0.18), (0, 0, 0.27), (0, -0.16, 0.33)], 0.11, fillet=0.09)
    lib.paint_white(elbow)
    barrel = s3d.at(s3d.cone("monitor_barrel", 0.11, 0.55, d2=0.085), y=-0.14, z=0.335, rx=85)
    nozzle = s3d.at(s3d.cone("monitor_nozzle", 0.09, 0.16, d2=0.06), y=-0.68, z=0.382, rx=85)
    lib.paint_white(barrel)
    lib.black_plastic(nozzle)
    grip = s3d.wire("monitor_grip", [(0.0, -0.42, 0.37), (0.0, -0.44, 0.45), (0.0, -0.30, 0.46)], 0.025, fillet=0.03)
    lib.black_plastic(grip)
    g = s3d.group("monitor", base, elbow, barrel, nozzle, grip)
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
    ant = s3d.wire("antenna", [(0.6, S.BODY_FRONT + 0.4, TOP), (0.6, S.BODY_FRONT + 0.4, TOP + 0.55)], 0.008)
    lib.black_plastic(ant)
    out.append(ant)
    return out


def build() -> dict:
    parts = deck() + hose_tray() + ladder() + monitor() + rails() + floodlights()
    return {"common": [s3d.group("Крыша", *parts)]}
