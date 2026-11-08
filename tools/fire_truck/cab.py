"""Кабина «как КамАЗ после рестайлинга» (форма своя, без марок): корпус с лобовым и боковыми стёклами,
швы дверей, решётка, бампер с фарами, белые крылья с арками и подножками, колпак с маячками, зеркала,
дворники, ручки."""
from __future__ import annotations

import math

import lib
import shapes
import spec as S
from lib import s3d

F, B = S.CAB_FRONT, S.CAB_BACK
HW = S.CAB_W / 2


def ws_frame(inset: float = 0.0):
    """Плоскость лобового стекла: начало в середине, нормаль наружу (вперёд и немного вверх)."""
    y0, z0 = F + 0.012, S.WS_BOTTOM
    y1, z1 = F + 0.012 + S.WS_LEAN, S.WS_TOP
    dy, dz = y1 - y0, z1 - z0
    L = math.hypot(dy, dz)
    n = (0.0, -dz / L, dy / L)
    o = (0.0, (y0 + y1) / 2 - n[1] * inset, (z0 + z1) / 2 - n[2] * inset)
    return s3d.Frame(o, n), L


def shell():
    """Корпус кабины: профиль сбоку, выдавленный на ширину, скругления углов и крыши."""
    pts = [(F, S.CAB_BOTTOM), (F + 0.012, S.WS_BOTTOM), (F + 0.012 + S.WS_LEAN, S.WS_TOP),
           (F + 0.30, S.CAB_ROOF), (B, S.CAB_ROOF), (B, S.CAB_BOTTOM)]
    prof = s3d.poly(pts, fillet=[0.0, 0.03, 0.10, 0.10, 0.04, 0.0])
    # скругление контура боков — последним (build): после него EXACT перестаёт резать борт −X
    return s3d.extrude("cab_shell", prof, S.CAB_W, both=True, on=lib.side(0))


def windshield(cab):
    fr, L = ws_frame()
    w, h = 2.06, L - 0.10
    rect = shapes.box_pts(-w / 2, w / 2, -h / 2, h / 2)
    s3d.pocket(cab, shapes.outline(rect, 0.10), 0.035, on=fr)
    seal = shapes.seal_ring("ws_seal", rect, 0.10, 0.022, 0.012, fr.offset(-0.035))
    g = s3d.extrude("windshield", shapes.outline(shapes.box_pts(-w / 2 + 0.01, w / 2 - 0.01, -h / 2 + 0.01, h / 2 - 0.01),
                                                0.09), 0.008, on=fr.offset(-0.028))
    lib.glass(g)
    return [seal, g]


def side_windows(cab):
    """Окна дверей: проём под стекло, уплотнитель, стекло с форточкой (стойка спереди)."""
    out = []
    w = S.SIDE_WIN
    for sgn in (1, -1):
        fr = lib.side(sgn * HW, sgn)
        rect = shapes.box_pts(min(sgn * w["y0"], sgn * w["y1"]), max(sgn * w["y0"], sgn * w["y1"]), w["z0"], w["z1"])
        s3d.pocket(cab, shapes.outline(rect, 0.05), 0.03, on=fr)
        out.append(shapes.seal_ring("side_seal", rect, 0.05, 0.018, 0.01, fr.offset(-0.03)))
        g = s3d.extrude("side_glass", shapes.outline(rect, 0.04), 0.006, on=fr.offset(-0.022))
        lib.glass(g)
        out.append(g)
        # стойка форточки
        yv = w["y0"] + 0.24
        post = s3d.box("vent_post", 0.012, 0.025, w["z1"] - w["z0"] - 0.03)
        lib.rubber(post)
        out.append(s3d.at(post, x=sgn * (HW - 0.02), y=yv, z=w["z0"] + 0.015))
    return out


def door_seams(cab):
    """Швы дверей и проём под ручку — резцом по контуру двери."""
    d = S.DOOR
    tools = []
    for sgn in (1, -1):
        fr = lib.side(sgn * HW, sgn)
        ya, yb = sorted((sgn * d["y0"], sgn * d["y1"]))
        rect = shapes.box_pts(ya, yb, d["z0"], d["z1"])
        tools.append(shapes.ring_tool("door_seam", rect, 0.06, 0.006, 0.012, fr))
        # горизонтальный шов под окном (накладка двери)
    s3d.cut(cab, tools)


def grille(cab):
    """Решётка: три чёрных щели, сужающиеся книзу, в красной панели; под ней — фальшпанель."""
    out = []
    slots = [(1.40, 1.54), (1.18, 1.42), (0.96, 1.30)]
    tools = []
    for w, z in slots:
        rect = shapes.box_pts(-w / 2, w / 2, z - 0.035, z + 0.035)
        tools.append(s3d.extrude("slot", shapes.outline(rect, 0.03), 0.10, both=True, on=lib.front(F)))
    s3d.cut(cab, tools)
    for w, z in slots:
        bar = s3d.fillet(s3d.box("grille_insert", w - 0.02, 0.03, 0.06), 0.012, edges="side")
        lib.black_plastic(bar)
        out.append(s3d.at(bar, y=F + 0.05, z=z - 0.03))
    # верхний обвод решётки и полосы «зубьями» — накладка из чёрного пластика между щелями
    rib = s3d.fillet(s3d.box("grille_rib", 1.50, 0.02, 0.02), 0.008, edges="side")
    lib.black_plastic(rib)
    out.append(s3d.at(rib, y=F - 0.002, z=1.62))
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
        fog = s3d.extrude("foglight", s3d.circle(0.09), 0.012, on=s3d.Frame((sx * 0.86, b["y0"] - 0.0, 0.56), (0, -1, 0)))
        lib.lens(fog, "#f3f3ea")
        s3d.pocket(body, shapes.outline(shapes.box_pts(sx * 0.86 - 0.06, sx * 0.86 + 0.06, 0.50, 0.62), 0.05), 0.02, on=fr)
        lamps += [lensp, reflector, ind, fog]
    s3d.pocket(body, shapes.outline(shapes.box_pts(-0.28, 0.28, 0.50, 0.63), 0.01), 0.012, on=fr)
    s3d.pocket(body, shapes.outline(shapes.box_pts(-0.45, 0.45, 0.64, 0.71), 0.02), 0.06, on=fr)
    lib.paint_white(body)
    lip = s3d.fillet(s3d.box("bumper_lip", b["w"] - 0.30, 0.20, 0.06), 0.03, edges="side")
    lib.black_plastic(lip)
    lip = s3d.at(lip, y=b["y0"] + 0.14, z=b["z0"] - 0.03)
    hooks = []
    for sx in (-1, 1):
        hk = s3d.at(s3d.torus("tow_hook", 0.09, 0.022), x=sx * 0.42, y=b["y0"] - 0.03, z=0.47, rx=90)
        lib.steel_dark(hk)
        hooks.append(hk)
    apron = s3d.fillet(s3d.box("front_apron", S.CAB_W - 0.06, 0.40, S.CAB_BOTTOM - b["z1"] + 0.03), 0.06, edges="side")
    lib.paint_red(apron)
    apron = s3d.at(apron, y=F + 0.20 + 0.001, z=b["z1"] - 0.03)
    return [body, lip, apron] + lamps + hooks


def arch_ring(name: str, r_out: float, r_in: float, length: float, x: float, y: float, z: float, keep: float):
    """Полукольцо арки осью вдоль X с центром (x, y, z): верхняя половина и ещё `keep` ниже оси."""
    ring = s3d.at(s3d.tube(name, 2 * r_out, 2 * r_in, length), z=-length / 2)
    # после поворота ry = 90 своя +X смотрит вниз: срезать x > keep (оставить верх)
    s3d.cut(ring, s3d.at(s3d.box(name + "_cut", 2.0, 2.0 * r_out + 0.2, length + 0.2), x=1.0 + keep, z=-length / 2 - 0.1))
    return s3d.at(ring, x=x, y=y, z=z, ry=90)


def fenders():
    """Белые крылья над передними колёсами: панель с аркой, чёрный расширитель, подножки за колесом."""
    f = S.FENDER
    out = []
    for sgn in (1, -1):
        panel = s3d.box("fender", f["t"], f["y1"] - f["y0"], f["z1"] - f["z0"])
        s3d.at(panel, x=sgn * (HW - f["t"] / 2 + 0.01), y=(f["y0"] + f["y1"]) / 2, z=f["z0"])
        arch = lib.along_x(s3d.cylinder("arch_cut", 2 * S.ARCH_R_F, 0.6), sgn * HW - 0.3, S.YF, S.WHEEL_Z)
        s3d.cut(panel, arch)
        lib.paint_white(panel)
        flare = arch_ring("arch_flare", S.ARCH_R_F + 0.05, S.ARCH_R_F - 0.005, f["t"] + 0.03,
                          sgn * (HW - f["t"] / 2 + 0.01), S.YF, S.WHEEL_Z, keep=0.12)
        lib.black_plastic(flare)
        # подножки: две ступени в задней части крыла, за колесом — ниша и рифлёная площадка
        fr = lib.side(sgn * (HW + 0.01), sgn)
        for z in S.STEPS_Z:
            ya, yb = sorted((sgn * (S.STEP_Y - 0.10), sgn * (S.STEP_Y + 0.10)))
            s3d.pocket(panel, shapes.outline(shapes.box_pts(ya, yb, z, z + 0.20), 0.02), 0.13, on=fr)
            tread = s3d.fillet(s3d.box("step", 0.15, 0.19, 0.025), 0.006, edges="side")
            lib.black_plastic(tread)
            out.append(s3d.at(tread, x=sgn * (HW - 0.07), y=S.STEP_Y, z=z))
        s3d.fillet(panel, 0.04, edges="side")
        out += [panel, flare]
        # колёсная ниша изнутри — чтобы сквозь крыло не просвечивала рама
        liner = arch_ring("wheel_house", S.ARCH_R_F + 0.02, S.ARCH_R_F + 0.005, 0.45, sgn * (HW - 0.38), S.YF,
                          S.WHEEL_Z, keep=0.0)
        lib.black_plastic(liner)
        out.append(liner)
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
        head = s3d.fillet(s3d.box("mirror", 0.07, 0.21, 0.38), 0.025, edges="side")
        s3d.fillet(head, 0.02, edges="top bottom")
        lib.black_plastic(head)
        head = s3d.at(head, x=sgn * (HW + 0.28), y=F + 0.50, z=2.28, rz=sgn * 10)
        glass_m = s3d.box("mirror_glass", 0.006, 0.19, 0.35)
        lib.chrome(glass_m)
        glass_m = s3d.at(glass_m, x=sgn * (HW + 0.28), y=F + 0.50 + 0.036, z=2.295, rz=sgn * 10 + 90)
        wide = s3d.fillet(s3d.box("mirror_wide", 0.07, 0.19, 0.17), 0.03, edges="side")
        lib.black_plastic(wide)
        wide = s3d.at(wide, x=sgn * (HW + 0.28), y=F + 0.50, z=2.08, rz=sgn * 10)
        out += [arm, head, glass_m, wide]
    kerb = s3d.fillet(s3d.box("mirror_kerb", 0.22, 0.07, 0.15), 0.03, edges="side")
    lib.black_plastic(kerb)
    out.append(s3d.at(kerb, x=-(HW - 0.20), y=F - 0.08, z=2.80, rx=-30))
    kerb_arm = s3d.wire("kerb_arm", [(-(HW - 0.20), F + 0.10, S.CAB_ROOF - 0.02), (-(HW - 0.20), F - 0.05, 2.90)], 0.018)
    lib.black_plastic(kerb_arm)
    out.append(kerb_arm)
    return out


def wipers():
    """Два дворника на лобовом стекле: оси у нижней кромки, рычаги вдоль стекла наискось."""
    fr, L = ws_frame(-0.012)
    out = []
    for xp in (-0.48, 0.38):
        p0 = fr.point(xp, -L / 2 + 0.06)
        p1 = fr.point(xp + 0.55, -L / 2 + 0.30)
        arm = s3d.wire("wiper", [tuple(p0), tuple(p1)], 0.014)
        blade = s3d.wire("wiper_blade", [tuple(fr.point(xp + 0.30, -L / 2 + 0.07)),
                                         tuple(fr.point(xp + 0.80, -L / 2 + 0.33))], 0.018)
        lib.black_plastic(arm)
        lib.rubber(blade)
        out += [arm, blade]
    return out


def handles_and_lamps():
    out = []
    for sgn in (1, -1):
        h = s3d.fillet(s3d.box("door_handle", 0.03, 0.17, 0.04), 0.012, edges="side")
        lib.black_plastic(h)
        out.append(s3d.at(h, x=sgn * (HW + 0.005), y=-1.86, z=1.82))
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
    for z in (0.69, 0.665):
        bar = s3d.fillet(s3d.box("bumper_intake_bar", 0.86, 0.02, 0.012), 0.005, edges="side")
        lib.black_plastic(bar)
        out.append(s3d.at(bar, y=b["y0"] + 0.02, z=z))
    for sx in (-1, 1):
        gut = s3d.fillet(s3d.box("rain_gutter", 0.018, B - F - 0.45, 0.022), 0.008, edges="side")
        lib.black_plastic(gut)
        out.append(s3d.at(gut, x=sx * (HW + 0.004), y=(F + 0.40 + B - 0.05) / 2, z=S.CAB_ROOF - 0.075))
    fr, L = ws_frame(-0.004)
    for xp in (-0.48, 0.38):
        piv = s3d.extrude("wiper_pivot", s3d.circle(0.045), 0.03, on=s3d.Frame(tuple(fr.point(xp, -L / 2 + 0.03)), tuple(fr.normal)))
        lib.black_plastic(piv)
        out.append(piv)
    # дефлекторы на передних стойках (чёрный пластик, как у КамАЗа): пластина вдоль скругления угла,
    # наклонена как стойка; профиль: x рамки — по −X мира, y — вперёд
    dy, dz = S.WS_LEAN, S.WS_TOP - S.WS_BOTTOM
    n = lib.unit(0.0, dy, dz)
    for sgn in (1, -1):
        pts = [(-sgn * 0.028, 0.0), (-sgn * 0.040, 0.0), (-sgn * 0.040, -0.17), (-sgn * 0.028, -0.17)]
        fin = s3d.extrude("pillar_deflector", s3d.poly(pts), (dz - 0.10) / n[2],
                          on=s3d.Frame((sgn * HW, F + 0.02 + 0.05 * dy / dz, S.WS_BOTTOM + 0.05), n))
        lib.black_plastic(fin)
        out.append(fin)
    spk = s3d.fillet(s3d.box("siren_speaker", 0.26, 0.16, 0.20), 0.03, edges="side")
    lib.black_plastic(spk)
    out.append(s3d.at(spk, x=-0.62, y=b["y1"] + 0.06, z=0.50))
    ant = s3d.wire("cab_antenna", [(0.85, B - 0.25, S.CAP_TOP), (0.85, B - 0.25, S.CAP_TOP + 0.45)], 0.007)
    lib.black_plastic(ant)
    base = s3d.cylinder("antenna_base", 0.05, 0.03)
    lib.black_plastic(base)
    out += [ant, s3d.at(base, x=0.85, y=B - 0.25, z=S.CAP_TOP)]
    return out


def build() -> dict:
    cab = shell()
    parts = windshield(cab) + side_windows(cab)
    door_seams(cab)
    parts += grille(cab)
    s3d.fillet(cab, 0.07, edges="top bottom")
    lib.paint_red(cab)
    parts = [cab] + parts + bumper() + fenders() + roof_cap() + mirrors() + wipers() + handles_and_lamps() + cab_details()
    return {"common": [s3d.group("Кабина", *parts)]}
