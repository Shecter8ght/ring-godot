"""Шасси: рама из двух швеллеров с поперечинами, мосты на рессорах, колёса, карданный вал,
глушитель с трубой, брызговики. Видно снизу и в арках."""
from __future__ import annotations

import lib
import spec as S
import wheels
from lib import s3d


def rail(sign: float):
    """Лонжерон-швеллер: стенка снаружи на FRAME_X, полки внутрь."""
    xo, w, h, t = S.FRAME_X, S.FRAME_W, S.FRAME_H, S.FRAME_T
    zt, zb = S.FRAME_TOP, S.FRAME_TOP - h
    pts = [(xo, zb), (xo, zt), (xo - w, zt), (xo - w, zt - t), (xo - t, zt - t), (xo - t, zb + t),
           (xo - w, zb + t), (xo - w, zb)]
    pts = [(sign * x, z) for x, z in pts]
    prof = s3d.poly([(-x, z) for x, z in pts], fillet=[0, 0, 0, 0, 0.006, 0.006, 0, 0])
    r = s3d.extrude("frame_rail", prof, S.FRAME_Y[1] - S.FRAME_Y[0], on=lib.rear(S.FRAME_Y[0]))
    frames = []
    for z in (zt - 0.07, zb + 0.07):
        y = S.FRAME_Y[0] + 0.12
        k = 0
        while y < S.FRAME_Y[1] - 0.10:
            if k % 9 not in (4, 5):                       # пропуски — места кронштейнов
                frames.append(s3d.Frame((sign * xo, y, z), (sign, 0, 0)))
            y += 0.10
            k += 1
    s3d.hole(r, 0.017, on=frames, depth=0.03)
    lib.steel_dark(r)
    return r


def crossmembers():
    out = []
    for y in (-2.95, -1.45, 0.2, 1.4, 2.75, 3.62):
        c = s3d.box("crossmember", 2 * (S.FRAME_X - S.FRAME_W) + 0.02, 0.09, 0.18)
        out.append(s3d.at(c, y=y, z=S.FRAME_TOP - 0.22))
    for c in out:
        lib.steel_dark(c)
    return out


def leaf_spring(y_mid: float, x: float, length: float, leaves: int):
    """Рессора: пакет листов, нижний короче; ушки на концах."""
    parts = []
    for i in range(leaves):
        L = length * (1.0 - 0.11 * i)
        leaf = s3d.fillet(s3d.box("leaf", 0.075, L, 0.013), 0.004, edges="side")
        parts.append(s3d.at(leaf, x=x, y=y_mid, z=S.FRAME_TOP - S.FRAME_H - 0.05 - 0.0135 * i))
    for sy in (-1, 1):
        parts.append(s3d.extrude("eye", s3d.circle(0.05), 0.08, both=True,
                                 on=lib.side(x, 1, y_mid + sy * length / 2, S.FRAME_TOP - S.FRAME_H - 0.035)))
    s3d.join(parts[0], *parts[1:])
    lib.steel_dark(parts[0])
    return parts[0]


def axle_front():
    beam = s3d.fillet(s3d.box("front_axle", S.TRACK_F - 0.30, 0.10, 0.12), 0.02, edges="side")
    s3d.at(beam, y=S.YF, z=S.WHEEL_Z - 0.10)
    parts = [beam]
    for sx in (-1, 1):
        king = s3d.cylinder("knuckle", 0.13, 0.26)
        parts.append(s3d.at(king, x=sx * (S.TRACK_F / 2 - 0.18), y=S.YF, z=S.WHEEL_Z - 0.13))
        spindle = lib.along_x(s3d.cylinder("spindle", 0.11, 0.16), 0.0, S.YF, S.WHEEL_Z)
        parts.append(s3d.at(spindle, x=sx * (S.TRACK_F / 2 - 0.16) - (0.16 if sx < 0 else 0)))
        parts.append(leaf_spring(S.YF, sx * (S.FRAME_X - 0.04), 1.45, 8))
    s3d.join(beam, *parts[1:])
    lib.steel_dark(beam)
    tie = s3d.wire("tie_rod", [(-S.TRACK_F / 2 + 0.22, S.YF + 0.16, S.WHEEL_Z - 0.06),
                               (S.TRACK_F / 2 - 0.22, S.YF + 0.16, S.WHEEL_Z - 0.06)], 0.035)
    lib.steel_dark(tie)
    return [beam, tie]


def axle_rear():
    tube = lib.along_x(s3d.cylinder("rear_axle", 0.16, S.TRACK_R - 0.25), -(S.TRACK_R - 0.25) / 2, S.YR, S.WHEEL_Z)
    diff = s3d.at(s3d.sphere("diff", 0.44), y=S.YR, z=S.WHEEL_Z - 0.22)
    nose = s3d.at(s3d.cone("diff_nose", 0.30, 0.22, d2=0.16), y=S.YR - 0.18, z=S.WHEEL_Z, rx=90)
    parts = [tube, diff, nose]
    for sx in (-1, 1):
        parts.append(leaf_spring(S.YR, sx * (S.FRAME_X - 0.04), 1.55, 10))
        drum = lib.along_x(s3d.cylinder("drum", 0.42, 0.20), 0.0, S.YR, S.WHEEL_Z)
        parts.append(s3d.at(drum, x=sx * (S.TRACK_R / 2 - 0.36) - (0.20 if sx < 0 else 0)))
    s3d.join(tube, *parts[1:])
    lib.steel_dark(tube)
    return [tube]


def place_wheel(w, x: float, y: float, outward: float):
    """Колесо осью вдоль X, наружной стороной (своей +Z) к `outward`."""
    return s3d.at(w, x=x, y=y, z=S.WHEEL_Z, ry=90 * outward)


def all_wheels():
    """Три колеса строятся один раз (протектор — долгий булев), остальные — копии."""
    proto = {"front": wheels.wheel("wheel_front", front=True),
             "out": wheels.wheel("wheel_rear_out", front=False),
             "in": wheels.wheel("wheel_rear_in", front=False, outer=False)}
    out = []
    for sx in (-1, 1):
        get = (lambda k: proto[k]) if sx > 0 else (lambda k: s3d.copy(proto[k]))
        out.append(place_wheel(get("front"), sx * S.TRACK_F / 2, S.YF, sx))
        out.append(place_wheel(get("out"), sx * (S.TRACK_R / 2 + S.DUAL / 2), S.YR, sx))
        out.append(place_wheel(get("in"), sx * (S.TRACK_R / 2 - S.DUAL / 2), S.YR, sx))
    return out


def driveline():
    engine = s3d.fillet(s3d.box("engine", 0.70, 1.20, 0.75), 0.06, edges="side top")
    s3d.at(engine, y=-2.55, z=0.62)
    gearbox = s3d.at(s3d.cone("gearbox", 0.42, 0.75, d2=0.30), y=-1.95, z=0.86, rx=-90)
    shaft = lib.along_y(s3d.cylinder("driveshaft", 0.09, 3.2), 0.0, -1.20, 0.70)
    s3d.join(engine, gearbox)
    lib.steel_dark(engine)
    lib.steel_dark(shaft)
    muffler = lib.along_y(s3d.fillet(s3d.cylinder("muffler", 0.32, 0.85), 0.03, edges="top bottom"),
                          -0.62, -1.45, 0.78)
    pipe = s3d.wire("exhaust", [(-0.62, -0.60, 0.78), (-0.62, 0.70, 0.78), (-0.95, 1.05, 0.60), (-1.12, 1.25, 0.58)],
                    0.09, fillet=0.15)
    lib.steel_dark(muffler)
    lib.steel_dark(pipe)
    return [engine, shaft, muffler, pipe]


def mudflaps():
    out = []
    for sx in (-1, 1):
        f = s3d.box("mudflap", 0.36, 0.008, 0.42)
        out.append(s3d.at(f, x=sx * (S.TRACK_F / 2), y=-1.50, z=0.16))
    for f in out:
        lib.rubber(f)
    return out


def suspension_details():
    """Амортизаторы переднего моста, стремянки рессор, тормозные камеры заднего моста, рулевой механизм
    с продольной тягой слева (виден в арке), задние брызговики."""
    out = []
    zr = S.FRAME_TOP - S.FRAME_H
    for sx in (-1, 1):
        x = sx * (S.FRAME_X + 0.06)
        sh = s3d.wire("shock", [(x, S.YF + 0.20, S.WHEEL_Z - 0.04), (x, S.YF + 0.32, zr + 0.02)], 0.06)
        lib.steel_dark(sh)
        out.append(sh)
        for y0 in (S.YF, S.YR):
            for dy in (-0.07, 0.07):
                xi, xo = sx * (S.FRAME_X - 0.085), sx * (S.FRAME_X + 0.005)
                ub = s3d.wire("u_bolt", [(xi, y0 + dy, zr - 0.05), (xi, y0 + dy, S.WHEEL_Z - 0.06),
                                         (xo, y0 + dy, S.WHEEL_Z - 0.06), (xo, y0 + dy, zr - 0.05)], 0.022, fillet=0.02)
                lib.steel_dark(ub)
                out.append(ub)
        cham = s3d.fillet(s3d.cylinder("brake_chamber", 0.17, 0.12), 0.02, edges="top bottom")
        lib.steel_dark(cham)
        out.append(s3d.at(cham, x=sx * (S.TRACK_R / 2 - 0.42), y=S.YR - 0.24, z=S.WHEEL_Z + 0.05, rx=90))
    box = s3d.fillet(s3d.box("steering_box", 0.16, 0.24, 0.20), 0.03, edges="side")
    lib.steel_dark(box)
    out.append(s3d.at(box, x=S.FRAME_X + 0.09, y=S.YF - 0.55, z=0.62))
    link = s3d.wire("drag_link", [(S.FRAME_X + 0.12, S.YF - 0.50, 0.58), (S.TRACK_F / 2 - 0.16, S.YF - 0.05, S.WHEEL_Z + 0.08)], 0.04)
    lib.steel_dark(link)
    out.append(link)
    for sx in (-1, 1):
        flap = s3d.box("mudflap_rear", 0.62, 0.008, 0.34)
        lib.rubber(flap)
        out.append(s3d.at(flap, x=sx * (S.TRACK_R / 2), y=S.YR + 0.80, z=0.16))
    return out


def frame_extras():
    """Ресиверы между лонжеронами, кронштейны и серьги рессор, тормозные шланги, крестовины карданного вала."""
    out = []
    for x, y in ((0.20, -0.75), (-0.20, -0.75)):
        tank = lib.along_y(s3d.fillet(s3d.cylinder("air_tank", 0.24, 0.62), 0.06, edges="top bottom"), x, y, S.FRAME_TOP - 0.30)
        lib.steel_dark(tank)
        out.append(tank)
    for y0 in (S.YF, S.YR):
        L = 1.45 if y0 == S.YF else 1.55
        for sx in (-1, 1):
            for sy in (-1, 1):
                hanger = s3d.fillet(s3d.box("spring_hanger", 0.10, 0.10, 0.12), 0.015, edges="side")
                lib.steel_dark(hanger)
                out.append(s3d.at(hanger, x=sx * (S.FRAME_X - 0.04), y=y0 + sy * L / 2, z=S.FRAME_TOP - S.FRAME_H - 0.08))
    for sx in (-1, 1):
        hose = s3d.wire("brake_hose", [(sx * S.FRAME_X, S.YR - 0.35, S.FRAME_TOP - 0.12),
                                       (sx * (S.FRAME_X + 0.10), S.YR - 0.30, S.WHEEL_Z + 0.25),
                                       (sx * (S.TRACK_R / 2 - 0.42), S.YR - 0.24, S.WHEEL_Z + 0.12)], 0.016, fillet=0.08)
        lib.rubber(hose)
        out.append(hose)
        hose_f = s3d.wire("brake_hose_front", [(sx * S.FRAME_X, S.YF - 0.20, S.FRAME_TOP - 0.12),
                                               (sx * (S.FRAME_X + 0.14), S.YF - 0.16, S.WHEEL_Z + 0.30),
                                               (sx * (S.TRACK_F / 2 - 0.20), S.YF - 0.12, S.WHEEL_Z + 0.10)], 0.016, fillet=0.08)
        lib.rubber(hose_f)
        out.append(hose_f)
    for y in (-1.20, 2.00 - 0.10):
        yoke = lib.along_y(s3d.fillet(s3d.cylinder("u_joint", 0.15, 0.10), 0.02, edges="top bottom"), 0.0, y - 0.05, 0.70)
        lib.steel_dark(yoke)
        out.append(yoke)
    bearing = s3d.fillet(s3d.box("center_bearing", 0.22, 0.10, 0.16), 0.02, edges="side")
    lib.steel_dark(bearing)
    out.append(s3d.at(bearing, y=0.40, z=0.64))
    return out


def build() -> dict:
    frame = [rail(1), rail(-1)] + crossmembers()
    parts = frame + axle_front() + axle_rear() + all_wheels() + driveline() + mudflaps() + suspension_details() + frame_extras()
    return {"common": [s3d.group("Шасси", *parts)]}
