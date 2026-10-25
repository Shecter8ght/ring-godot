"""Транспорт «Проспекта»: панели кузова легковой четырёхдверной машины (шаблон для всех классов).

Состав (левый борт, правый — зеркалом): капот, короб под лобовым, крылья, фары, передний бампер
с проёмами, двери передняя и задняя (обшивка ниже пояса, рамка окна, стекло), боковина (стойки,
рейлинг крыши, порог, заднее крыло), крыша, лобовое и заднее стёкла, крышка багажника (седан)
или пятая дверь (хэтчбек, универсал), фонари, задний бампер с нишей номера.

Каждая деталь — (имя, материал, вершины, грани, узел). Узел — что открывается вместе:
body, door_fl/door_fr/door_rl/door_rr, hood, lid. Шарниры узлов — hinges() ниже.
Числа раскладки — spec["lay"] (specs.py); всё, что можно взять из поля формы (край стекла,
край крыши, пояс), берётся из поля — тогда раскладка переносится между классами.
"""
from __future__ import annotations

import math

import numpy as np

from vlib import (Seam, View, arch_pt, arch_pts, cut, domain_panel, fillet_poly, lift_poly, loop, mirror_curve,
                  mirror_mesh, phi_at_z, resample, sym_loop)

GAP = 0.0045
GAP_TIGHT = 0.0035
DEBUG: list = []           # панели, которые не собрались: (имя, вид, контур uv, проёмы uv)


class Geo:
    """Где на кузове пояс, края стёкол и крыши — по кривым поля."""

    def __init__(self, f, s: dict) -> None:
        self.f, self.s = f, s

    def belt_side(self, y: float) -> float:
        return float(self.f.top(y)) - self.s["crown_hood"]

    def cabin_half(self, y: float, z: float) -> float:
        f = self.f
        belt, roof = float(f.belt(y)), float(f.roof(y))
        g0, g1 = float(f.gh(y)), float(f.gh_top(y))
        rise = max(roof - belt, 0.15)
        return g0 - (g0 - g1) / rise * max(z - belt, 0.0)

    def ws_pt(self, z: float, frac: float) -> tuple:
        y = float(self.f.ws(z)) + float(self.f.ws_sw(frac))
        return ("p", frac * self.cabin_half(y, z), y, z)

    def bl_pt(self, z: float, frac: float) -> tuple:
        y = float(self.f.bl(z)) - float(self.f.bl_sw(frac))
        return ("p", frac * self.cabin_half(y, z), y, z)

    def roof_pt(self, y: float, frac: float) -> tuple:
        return ("p", frac * float(self.f.gh_top(y)), y, float(self.f.roof(y)) - 0.01)


def build(surf, f, s: dict, views: dict) -> tuple[list, dict]:
    """Все панели кузова. Возвращает (детали, швы) — швы нужны деталям и вариантам."""
    lay = s["lay"]
    g = Geo(f, s)
    out: list = []
    S: dict = {}
    yf, yr = s["wheel_y"]
    wz = s["wheel_z"]
    ar = s["arch_r"] + 0.004                       # кромка арки чуть снаружи выреза поля

    def sm(name, pts, view, **kw):
        S[name] = Seam(surf, views, pts, view, **kw)
        return S[name]

    def panel(name, mat, view, outer, group="body", holes=(), mirror=True, **kw):
        import vq
        V = None
        h0 = kw.pop("h", 0.014) * vq.Q["h"]
        kw.setdefault("roll_steps", vq.Q["roll"])
        for k in range(4):                          # совпадение узлов сетки с контуром — другой шаг
            try:
                V, F = domain_panel(surf, views[view], outer, holes=holes, h=h0 * (1 + 0.07 * k), **kw)
                break
            except Exception as e:
                err = e
        if V is None:                               # отладка раскладки: контуры на вид — в DEBUG
            print(f"!! панель {name}: {err}")
            DEBUG.append((name, view, views[view].to_uv(outer), [views[view].to_uv(hh) for hh in holes]))
            return None, None
        side = "L" if mirror else ""
        out.append((name + ("_" + side if side else ""), mat, V, F, group + ("l" if mirror and group != "body" else "")))
        if mirror:
            Vm, Fm = mirror_mesh(V, F)
            out.append((name + "_R", mat, Vm, Fm, group + ("r" if group != "body" else "")))
        return V, F

    # ============================================================== перёд: капот, фары, бампер, крыло
    hood_c = ("top", 0.0, lay["hood_front_y"])
    lamp_in_top = ("top", *lay["lamp_in_top"])
    lamp_out_top = ("top", *lay["lamp_out_top"])
    hood_rear_l = ("top", *lay["hood_rear_corner"])
    cowl_c = ("top", 0.0, lay["cowl_y"])
    lamp_tip = ("side", *lay["lamp_tip"])
    lamp_in_bot = ("front", *lay["lamp_in_bot"])
    phi_b = lay["arch_f_bump_phi"]
    arch_bump = arch_pt(yf, wz, ar, phi_b)
    phi_fb = phi_at_z(wz, ar, lay["bump_bottom_z"], True)
    arch_bot_f = ("side", yf + ar * math.cos(math.radians(phi_fb)), lay["bump_bottom_z"])
    sill_top_z, sill_bot_z = lay["sill_top_z"], lay["sill_bot_z"]
    phi_sf = phi_at_z(wz, ar, sill_top_z, False)
    arch_sill_f = ("side", yf + ar * math.cos(math.radians(phi_sf)), sill_top_z)
    door_fb = ("side", lay["door_f_y"], sill_top_z + 0.004)
    door_ft = ("side", lay["door_f_y"] + 0.012, g.belt_side(lay["door_f_y"]) - 0.002)

    sm("cowl", [cowl_c, ("top", 0.42, lay["cowl_y"] + 0.022), hood_rear_l], "top")
    sm("hood_side", [hood_rear_l] + [("top", *p) for p in lay["hood_side"]] + [lamp_out_top], "top")
    sm("hood_lamp", [lamp_out_top] + [("top", *p) for p in lay["hood_lamp"]] + [lamp_in_top], "top")
    sm("hood_front", [lamp_in_top, ("top", lay["lamp_in_top"][0] * 0.5, lay["hood_front_y"] - 0.002), hood_c], "top")
    sm("lamp_top_out", [lamp_out_top] + [("side", *p) for p in lay["lamp_top_side"]] + [lamp_tip], "rf")
    sm("lamp_bottom", [lamp_tip] + [("side", *p) for p in lay["lamp_bot_side"]]
       + [("front", *p) for p in lay["lamp_bot_front"]] + [lamp_in_bot], "rf")
    sm("lamp_inner", [lamp_in_bot] + [("front", *p) for p in lay["lamp_inner"]] + [lamp_in_top], "rf")
    sm("bump_fender", [lamp_tip] + [("side", *p) for p in lay["bump_fender"]] + [arch_bump], "side")
    sm("arch_f_front", [arch_bump] + arch_pts(yf, wz, ar, phi_b, phi_fb, 9)[1:-1] + [arch_bot_f], "side")
    sm("arch_f_top", [arch_bump] + arch_pts(yf, wz, ar, phi_b, phi_sf, 13)[1:-1] + [arch_sill_f], "side")
    sm("sill_f", [arch_sill_f, ("side", (arch_sill_f[1] + door_fb[1]) / 2, sill_top_z + 0.002), door_fb], "side")
    sm("door_front", [door_fb, ("side", lay["door_f_y"] - 0.004, 0.55), ("side", lay["door_f_y"] + 0.004, 0.80), door_ft],
       "side")
    sm("fender_apillar", [door_ft, ("p", *_mid3(surf, views, door_ft, hood_rear_l)), hood_rear_l], "rs")

    hood = sym_loop([S["cowl"].P, S["hood_side"].P, S["hood_lamp"].P, S["hood_front"].P])
    S["_hood_loop"] = hood
    panel("Hood", "paint", "top", hood, group="hood", mirror=False, h=0.016, gap=GAP)
    fender = loop([S["door_front"].reversed(), S["sill_f"].reversed(), S["arch_f_top"].reversed(),
                   S["bump_fender"].reversed(), S["lamp_top_out"].reversed(), S["hood_side"].reversed(),
                   S["fender_apillar"].reversed()])
    panel("Fender", "paint", "rs", fender, h=0.014, gap=GAP)
    lamp = loop([S["hood_lamp"].P, S["lamp_inner"].reversed(), S["lamp_bottom"].reversed(), S["lamp_top_out"].reversed()])
    S["_lamp_loop"] = lamp
    panel("Headlamp", "lamp_glass", "rf", lamp, h=0.009, gap=GAP_TIGHT, flange=0.035)

    splitter_c = ("front", 0.0, lay["bump_bottom_z"])
    sm("bump_bottom", [arch_bot_f] + [("front", *p) for p in lay["bump_bottom_front"]] + [splitter_c], "rf")
    bl_ = [S["hood_front"].reversed(), S["lamp_inner"].reversed(), S["lamp_bottom"].reversed(), S["bump_fender"].P,
           S["arch_f_front"].P, S["bump_bottom"].P]
    bumper = loop(bl_ + [mirror_curve(c)[::-1] for c in reversed(bl_)])
    holes = []
    S["_front_holes"] = {}
    for key in ("grille", "intake", "fog"):
        if key not in lay:
            continue
        pts = lay[key]
        if key == "fog":
            for sgn, nm in ((1, "fog_l"), (-1, "fog_r")):
                P = Seam(surf, views, [("front", sgn * x, z) for x, z in pts][:: sgn], "rf", n=200, closed=True).P
                holes.append(P)
                S["_front_holes"][nm] = P
            continue
        full = [("front", x, z) for x, z in pts] + [("front", -x, z) for x, z in reversed(pts[1:-1])]
        P = Seam(surf, views, full, "rf", n=500, closed=True).P
        holes.append(P)
        S["_front_holes"][key] = P
    panel("Bumper_F", "bumper", "rf", bumper, mirror=False, holes=holes, h=0.014, gap=GAP_TIGHT, hole_depth=0.07)

    # ============================================================== кабина: стёкла, крыша
    z_wsb = lay["ws_base_z"]
    ws_base_c = ("p", 0.0, float(f.ws(z_wsb)), z_wsb)
    ws_base_l = g.ws_pt(z_wsb + 0.012, lay["glass_frac"])
    z_wst = lay["ws_top_z"]
    ws_top_l = g.ws_pt(z_wst, lay["glass_frac"] - 0.02)
    ws_top_c = ("p", 0.0, float(f.ws(z_wst + 0.006)), z_wst + 0.006)
    zs = np.linspace(z_wsb + 0.012, z_wst, 6)
    sm("ws_base", [ws_base_c, ("p", 0.35, float(f.ws(z_wsb)) + float(f.ws_sw(0.45)), z_wsb), ws_base_l], "ws")
    sm("ws_side", [g.ws_pt(z, lay["glass_frac"] - 0.02 * (z - zs[0]) / (zs[-1] - zs[0])) for z in zs], "ws")
    sm("ws_top", [ws_top_l, ("p", 0.30, float(f.ws(z_wst)) + float(f.ws_sw(0.5)), z_wst + 0.004), ws_top_c], "ws")
    sm("cowl_side", [hood_rear_l, ("p", *_mid3(surf, views, hood_rear_l, ws_base_l)), ws_base_l], "top")

    # седан: край заднего стекла; хэтчбек и универсал: край пятой двери (стекло — проём в ней)
    z_blt, z_blb = lay["bl_top_z"], lay["bl_base_z"]
    rf_ = lay.get("tg_frac", lay["glass_frac"])
    bl_top_l = g.bl_pt(z_blt, rf_ - 0.03)
    bl_top_c = ("p", 0.0, float(f.bl(z_blt + 0.004)), z_blt + 0.004)
    bl_bot_l = g.bl_pt(z_blb, rf_ - 0.01)
    bl_bot_c = ("p", 0.0, float(f.bl(z_blb)), z_blb)
    zb = np.linspace(z_blb, z_blt, 6)
    sm("bl_side", [g.bl_pt(z, rf_ - 0.01 - 0.02 * (z - zb[0]) / (zb[-1] - zb[0])) for z in zb][::-1], "bl")
    sm("bl_top", [bl_top_l, ("p", 0.28, float(f.bl(z_blt)) - float(f.bl_sw(0.5)), z_blt + 0.003), bl_top_c], "bl")
    sm("bl_bot", [bl_bot_l, ("p", 0.30, float(f.bl(z_blb)) - float(f.bl_sw(0.5)), z_blb), bl_bot_c], "bl")
    ys = np.linspace(S["ws_top"].P[0][1], S["bl_side"].P[0][1], 7)
    sm("roof_side", [("p", *S["ws_top"].P[0])] + [g.roof_pt(y, lay["roof_frac"]) for y in ys[1:-1]]
       + [("p", *S["bl_side"].P[0])], "top")

    ws = sym_loop([S["ws_base"].P, S["ws_side"].P, S["ws_top"].P])
    panel("Glass_Windshield", "glass", "ws", ws, mirror=False, h=0.02, gap=0.006, flange=0.02, fit_deg=4, fit_blend=0.05)
    blp = sym_loop([S["bl_bot"].reversed(), S["bl_side"].reversed(), S["bl_top"].P])
    if s["rear_style"] == "sedan":
        panel("Glass_Rear", "glass", "bl", blp, mirror=False, h=0.02, gap=0.006, flange=0.02, fit_deg=4, fit_blend=0.05)
    roof = sym_loop([S["ws_top"].reversed(), S["roof_side"].P, S["bl_top"].P])
    S["_roof_loop"] = roof
    panel("Roof", "paint", "top", roof, mirror=False, h=0.02, gap=0.003)
    cowl = sym_loop([S["cowl"].P, S["cowl_side"].P, S["ws_base"].reversed()])
    panel("Cowl", "trim_black", "top", cowl, mirror=False, h=0.012, gap=GAP)

    # ============================================================== двери
    _doors(surf, f, s, views, g, S, sm, panel, out)
    # ============================================================== корма
    _rear(surf, f, s, views, g, S, sm, panel, out)
    return out, S


def _mid3(surf, views, a, b) -> np.ndarray:
    from vlib import point3
    pa, pb = point3(surf, views, a), point3(surf, views, b)
    return surf.project(((pa + pb) / 2)[None])[0]


def _doors(surf, f, s, views, g, S, sm, panel, out) -> None:
    """Передняя и задняя двери: обшивка ниже пояса, рамка окна, стекло; боковина — вокруг."""
    lay = s["lay"]
    yf, yr = s["wheel_y"]
    wz = s["wheel_z"]
    ar = s["arch_r"] + 0.004
    sill_top = lay["sill_top_z"]
    yd_f, yb, yc_belt = lay["door_f_y"], lay["b_y"], lay["c_belt_y"]
    belt = g.belt_side
    top_drop = lay["door_top_drop"]

    def top_z(y):
        return float(f.roof(y)) - top_drop

    door_ft = S["door_front"].P[-1]
    door_fb = S["door_front"].P[0]
    frame_base = ("side", lay["frame_base_y"], belt(lay["frame_base_y"]) + 0.004)
    a_top = ("side", lay["a_top_y"], top_z(lay["a_top_y"]))
    b_top = ("side", yb, top_z(yb))
    b_bot = ("side", yb + 0.004, sill_top + 0.004)
    c_top = ("side", lay["c_top_y"], top_z(lay["c_top_y"]))
    c_belt = ("side", yc_belt, belt(yc_belt) - 0.002)

    sm("door_belt_f", [("p", *door_ft), ("side", (door_ft[1] + lay["frame_base_y"]) / 2, belt((door_ft[1] + lay["frame_base_y"]) / 2) + 0.002),
                       frame_base], "side")
    sm("frame_a", [frame_base] + [("side", *p) for p in lay["frame_a"]] + [a_top], "side")
    ys = np.linspace(lay["a_top_y"], yb, 5)
    sm("door_top_f", [a_top] + [("side", y, top_z(y)) for y in ys[1:-1]] + [b_top], "side")
    ys = np.linspace(yb, lay["c_top_y"], 5)
    sm("door_top_r", [b_top] + [("side", y, top_z(y)) for y in ys[1:-1]] + [c_top], "side")
    sm("frame_c", [c_top] + [("side", *p) for p in lay["frame_c"]] + [c_belt], "side", smooth=False, n=120)
    # задняя кромка задней двери: вниз от пояса и вокруг арки с отступом
    r_off = ar + lay["door_arch_off"]
    phi_d = phi_at_z(wz, r_off, sill_top + 0.004, True)
    rear_edge = [c_belt] + [("side", *p) for p in lay["door_r_edge"]] + \
        arch_pts(yr, wz, r_off, lay["door_arch_phi0"], phi_d, 7)
    sm("door_rear", rear_edge, "side")
    S["door_rear"].P[-1] = S["door_rear"].P[-1]
    door_rb3 = S["door_rear"].P[-1]
    sm("door_bot_r", [("p", *door_rb3), ("side", (door_rb3[1] + yb) / 2, sill_top + 0.004), b_bot], "side")
    sm("door_bot_f", [b_bot, ("side", (yb + yd_f) / 2, sill_top + 0.004), ("p", *door_fb)], "side")
    sm("b_line", [b_bot, ("side", yb + 0.004, 0.6), ("side", yb, belt(yb)), b_top], "side")

    # Обшивка ниже пояса и рамка окна — отдельные панели (стык прикрыт уплотнителем пояса)
    def belt_cut(y0, y1, n=6):
        return [("side", y, belt(y) + 0.002) for y in np.linspace(y0, y1, n)]

    # передняя дверь
    yb_belt = S["b_line"].P[np.argmin(np.abs(S["b_line"].P[:, 2] - belt(yb)))]
    fb3 = S["door_belt_f"].P[-1]
    sm("belt_f", [("p", *fb3)] + belt_cut(fb3[1] + 0.05, yb - 0.05, 5)[1:-1] + [("p", *yb_belt)], "side")
    b_low = Seam(surf, views, [b_bot, ("side", yb + 0.004, 0.6), ("p", *yb_belt)], "side").P
    b_up = Seam(surf, views, [("p", *yb_belt), ("side", yb, (belt(yb) + top_z(yb)) / 2), b_top], "side").P
    S["b_low"], S["b_up"] = b_low, b_up
    skin_f = loop([S["door_front"].P, S["door_belt_f"].P, S["belt_f"].P, b_low[::-1], S["door_bot_f"].P])
    panel("Door_F_Skin", "paint", "side", skin_f, group="door_f", h=0.014, gap=GAP, flange=lay["door_depth"])
    S["_skin_f"] = skin_f
    # окно открыто к поясу: рамка П-образная, стекло уходит в дверь под уплотнитель пояса
    wf, (bA, bB, bC) = _window(surf, views, lay["win_f"], S["belt_f"].P, lay.get("win_r_corner", 0.035))
    S["_win_f"], S["belt_f_parts"] = wf, (bA, bB, bC)
    frame_f = loop([S["frame_a"].P, S["door_top_f"].P, b_up[::-1], bC[::-1], wf[::-1], bA[::-1]])
    panel("Door_F_Frame", "paint", "side", frame_f, group="door_f", h=0.010, gap=GAP, flange=0.03)
    panel("Glass_Door_F", "glass", "side", loop([wf, bB[::-1]]), group="door_f", h=0.018, gap=0.004,
          flange=0.02, fit_deg=3, fit_blend=0.03)
    # задняя дверь
    yc = S["door_rear"].P[0]
    sm("belt_r", [("p", *yb_belt)] + belt_cut(yb + 0.05, yc[1] - 0.04, 5)[1:-1] + [("p", *yc)], "side")
    ys_b = np.linspace(yb, float(f.rear.knots[-1, 1]), 40)
    S["_belt_side"] = np.c_[ys_b, [belt(y) for y in ys_b]]
    skin_r = loop([b_low, S["belt_r"].P, S["door_rear"].P, S["door_bot_r"].P])
    panel("Door_R_Skin", "paint", "side", skin_r, group="door_r", h=0.014, gap=GAP, flange=lay["door_depth"])
    S["_skin_r"] = skin_r
    wr, (rA, rB, rC) = _window(surf, views, lay["win_r"], S["belt_r"].P, lay.get("win_r_corner", 0.035))
    S["_win_r"], S["belt_r_parts"] = wr, (rA, rB, rC)
    frame_r = loop([b_up, S["door_top_r"].P, S["frame_c"].P, rC[::-1], wr[::-1], rA[::-1]])
    panel("Door_R_Frame", "paint", "side", frame_r, group="door_r", h=0.010, gap=GAP, flange=0.03)
    panel("Glass_Door_R", "glass", "side", loop([wr, rB[::-1]]), group="door_r", h=0.018, gap=0.004,
          flange=0.02, fit_deg=3, fit_blend=0.03)


def _window(surf, views, corners, belt_curve: np.ndarray, r: float):
    """Окно двери: углы на виде сбоку (Y, Z), первый и последний — на поясе (Z = None).

    Возвращает кривую окна от переднего нижнего угла вверх, поверху и вниз к заднему нижнему углу
    (концы — точно на поясе) и пояс, разрезанный углами окна: до окна, под окном, после окна.
    """
    side = views["side"]
    belt_uv = side.to_uv(belt_curve)
    pts = []
    for y, z in corners:
        if z is None:
            z = float(np.interp(y, belt_uv[:, 0], belt_uv[:, 1]))
        pts.append((y, z))
    uv = fillet_poly(pts, r)
    W = lift_poly(surf, side, uv)
    i0 = int(np.argmin(np.linalg.norm(belt_curve - W[0], axis=1)))
    i1 = int(np.argmin(np.linalg.norm(belt_curve - W[-1], axis=1)))
    W[0], W[-1] = belt_curve[i0], belt_curve[i1]
    a, b = sorted((i0, i1))
    return W, (belt_curve[:a + 1], belt_curve[a:b + 1], belt_curve[b:])


def _rear(surf, f, s, views, g, S, sm, panel, out) -> None:
    """Корма седана: крышка багажника, фонари, задний бампер; боковина (стойки, заднее крыло, порог)."""
    lay = s["lay"]
    yf, yr = s["wheel_y"]
    wz = s["wheel_z"]
    ar = s["arch_r"] + 0.004
    sill_top, sill_bot = lay["sill_top_z"], lay["sill_bot_z"]
    bl_bot_l = S["bl_bot"].P[0]
    tl_in_top = ("rear", *lay["tl_in_top"])
    tl_in_bot = ("rear", *lay["tl_in_bot"])
    tl_tip = ("side", *lay["tl_tip"])
    lid_bot_c = ("rear", 0.0, lay["lid_bot_z"])
    lid_bot_l = ("rear", lay["tl_in_bot"][0] - 0.01, lay["lid_bot_z"])
    phi_rb = lay["arch_r_bump_phi"]
    arch_bump_r = arch_pt(yr, wz, ar, phi_rb)
    phi_rbot = phi_at_z(wz, ar, lay["bump_r_bottom_z"], False)
    arch_bot_r = ("side", yr + ar * math.cos(math.radians(phi_rbot)), lay["bump_r_bottom_z"])

    hatch = s["rear_style"] != "sedan"
    # крышка багажника: от основания заднего стекла по деке, вниз по корме вдоль фонаря до бампера;
    # у пятой двери — от пояса на стойке D вниз к фонарю
    sm("lid_upper", [("p", *bl_bot_l)] + [("top", *p) for p in lay.get("lid_top", [])]
       + [("rear", *p) for p in lay.get("lid_rear", [])] + [tl_in_top], "rx_rear")
    sm("lid_lamp", [tl_in_top, ("rear", (lay["tl_in_top"][0] + lay["tl_in_bot"][0]) / 2 + 0.004,
                                (lay["tl_in_top"][1] + lay["tl_in_bot"][1]) / 2), tl_in_bot], "rear")
    sm("lid_side_low", [tl_in_bot, lid_bot_l], "rear", smooth=False, n=40)
    sm("lid_lower", [lid_bot_l, ("rear", lay["tl_in_bot"][0] * 0.5, lay["lid_bot_z"] - 0.002), lid_bot_c], "rear")
    sm("tl_top", [tl_in_top] + [("rear", *p) for p in lay["tl_top_rear"]] + [("side", *p) for p in lay["tl_top_side"]]
       + [tl_tip], "rr")
    sm("tl_bot", [tl_in_bot] + [("rear", *p) for p in lay["tl_bot_rear"]] + [("side", *p) for p in lay["tl_bot_side"]]
       + [tl_tip], "rr")
    sm("bump_quarter", [tl_tip] + [("side", *p) for p in lay["bump_quarter"]] + [arch_bump_r], "side")
    phi_sr = phi_at_z(wz, ar, sill_bot + 0.01, True)
    arch_sill_r_bot = ("side", yr + ar * math.cos(math.radians(phi_sr)), sill_bot + 0.01)
    sm("arch_r_top", [arch_bump_r] + arch_pts(yr, wz, ar, phi_rb, phi_sr, 15)[1:-1] + [arch_sill_r_bot], "side")
    sm("arch_r_low", [arch_bump_r] + arch_pts(yr, wz, ar, phi_rb, phi_rbot, 7)[1:-1] + [arch_bot_r], "side")
    sm("bump_r_bottom", [arch_bot_r] + [("rear", *p) for p in lay["bump_r_bottom_rear"]]
       + [("rear", 0.0, lay["bump_r_bottom_z"] + 0.02)], "rr")
    # порог снизу: от задней арки к передней
    phi_sf_bot = phi_at_z(wz, ar, sill_bot + 0.01, False)
    arch_sill_f_bot = ("side", yf + ar * math.cos(math.radians(phi_sf_bot)), sill_bot + 0.01)
    sm("sill_bottom", [arch_sill_r_bot, ("side", 0.0, sill_bot), arch_sill_f_bot], "side")
    arch_sill_f = S["sill_f"].P[0]
    sm("arch_f_sill", [arch_sill_f_bot] + arch_pts(yf, wz, ar, phi_sf_bot, phi_at_z(wz, ar, lay["sill_top_z"], False), 5)[1:-1]
       + [("p", *arch_sill_f)], "side")
    sm("lid_side_top", [("p", *S["bl_side"].P[-1]), ("p", *bl_bot_l)], "top", smooth=False, n=20)

    # --- крышка (пятая дверь) и фонари
    if hatch:
        lid = sym_loop([S["bl_top"].reversed(), S["bl_side"].P, S["lid_upper"].P, S["lid_lamp"].P, S["lid_side_low"].P,
                        S["lid_lower"].P])
        glass = _tail_glass(surf, views, g, lay)
        S["_lid_loop"], S["_tg_glass"] = lid, glass
        panel("Tailgate" if s["rear_style"] != "suv" else "Rear_Door", "paint", "rx_rear", lid, group="lid",
              mirror=False, holes=[glass], h=0.016, gap=GAP, flange=0.03, hole_depth=0.03)
        panel("Glass_Rear", "glass", "bl", glass, group="lid", mirror=False, h=0.02, gap=0.005, flange=0.02, fit_deg=3,
              fit_blend=0.04)
    else:
        lid = sym_loop([S["bl_bot"].reversed(), S["lid_upper"].P, S["lid_lamp"].P, S["lid_side_low"].P,
                        S["lid_lower"].P])
        S["_lid_loop"] = lid
        panel("Trunk_Lid", "paint", "rx_rear", lid, group="lid", mirror=False, h=0.016, gap=GAP, flange=0.03)
    tl = loop([S["lid_lamp"].P, S["tl_bot"].P, S["tl_top"].reversed()])
    S["_tl_loop"] = tl
    panel("Taillamp", "lamp_red", "rr", tl, h=0.009, gap=GAP_TIGHT, flange=0.035)
    # --- задний бампер с нишей номера
    bump = sym_loop([S["lid_lower"].reversed(), S["lid_side_low"].reversed(), S["tl_bot"].P, S["bump_quarter"].P,
                     S["arch_r_low"].P, S["bump_r_bottom"].P])
    plate = [("rear", x, z) for x, z in lay["plate_r"]]
    plate = plate + [("rear", -x, z) for _, x, z in reversed(plate[1:-1])]
    plate_loop = Seam(surf, views, plate, "rear", n=300, closed=True).P
    S["_plate_r"] = plate_loop
    panel("Bumper_R", "bumper", "rr", bump, mirror=False, holes=[plate_loop], h=0.014, gap=GAP_TIGHT, hole_depth=0.03)

    # --- боковина: стойки A и C, рейлинг крыши, порог, заднее крыло (вокруг дверей)
    _bodyside(surf, s, views, S, sm, panel)


def _tail_glass(surf, views, g, lay) -> np.ndarray:
    """Стекло пятой двери: четыре угла (верх и низ — свои доли ширины), скругления, на плоском виде стекла."""
    bl = views["bl"]
    (zt, ft), (zb, fb) = lay["tg_glass_top"], lay["tg_glass_bot"]
    pts = []
    for z, fr in ((zb, fb), (zt, ft)):
        p = g.bl_pt(z, fr)
        pts.append(surf.project(np.array([p[1:4]]))[0])
    bl_l, tl_l = pts
    corners = [bl_l, tl_l, tl_l * [-1, 1, 1], bl_l * [-1, 1, 1]]
    uv = bl.to_uv(np.array(corners))
    if (uv[1, 0] - uv[0, 0]) * 0 + _area(uv) < 0:
        uv = uv[::-1]
    from vlib import fillet_poly, lift_poly
    ring = fillet_poly(uv, lay.get("tg_glass_r", 0.05), closed=True)
    P = lift_poly(surf, bl, np.vstack([ring, ring[:1]]))
    return P[:-1]


def _area(uv: np.ndarray) -> float:
    x, y = uv[:, 0], uv[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def _bodyside(surf, s, views, S, sm, panel) -> None:
    side = loop([
        S["fender_apillar"].P,            # от верха передней кромки двери к углу капота
        S["cowl_side"].P,                 # угол капота → угол лобового
        S["ws_side"].P,                   # стойка A
        S["roof_side"].P,                 # край крыши
        S["bl_side"].P,                   # стойка C (край заднего стекла сверху вниз)
        S["lid_upper"].P,                 # край крышки багажника → внутренний верх фонаря
        S["tl_top"].P,                    # верх фонаря → хвост на борту
        S["bump_quarter"].P,              # от хвоста фонаря шов бампера → арка
        S["arch_r_top"].P,                # над задним колесом → низ порога
        S["sill_bottom"].P,               # низ порога вперёд
        S["arch_f_sill"].P,               # передняя арка снизу → верх порога
        S["sill_f"].P,                    # шов крыла по порогу → низ передней кромки двери
        S["door_bot_f"].reversed(),       # низ передней двери
        S["door_bot_r"].reversed(),       # низ задней двери
        S["door_rear"].reversed(),        # задняя кромка задней двери вверх к поясу
        S["frame_c"].reversed(),          # рамка у стойки C вверх
        S["door_top_r"].reversed(),       # верх задней двери вперёд
        S["door_top_f"].reversed(),       # верх передней двери вперёд
        S["frame_a"].reversed(),          # рамка вдоль стойки A вниз
        S["door_belt_f"].reversed(),      # по поясу к передней кромке двери
    ])
    S["_side_loop"] = side
    holes = []
    lay = s["lay"]
    if "quarter_win" in lay:
        # заднее боковое окно (универсал, внедорожник): проём в боковине и стекло в нём
        side_v = views["side"]
        belt_y = lambda y: float(np.interp(y, S["_belt_side"][:, 0], S["_belt_side"][:, 1]))  # noqa: E731
        pts = [(y, belt_y(y) + 0.012 if z is None else z) for y, z in lay["quarter_win"]]
        from vlib import fillet_poly, lift_poly
        ring = fillet_poly(pts, lay.get("quarter_r", 0.035), closed=True)
        Q = lift_poly(surf, side_v, np.vstack([ring, ring[:1]]))[:-1]
        holes.append(Q)
        S["_quarter_win"] = Q
    panel("Bodyside", "paint", "rs", side, h=0.016, gap=GAP, holes=holes, hole_depth=0.03)
    if holes:
        panel("Glass_Quarter", "glass", "side", holes[0], h=0.018, gap=0.004, flange=0.02, fit_deg=3, fit_blend=0.03)
